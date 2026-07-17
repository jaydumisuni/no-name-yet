"""Blind review-quality benchmark for Sergeant.

Only repository files enter the temporary review workspace. Expected findings
stay outside the workspace and are used after review for scoring.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sysconfig
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from .pr_reviewer import run_independent_pr_review
from .production_hardening import HardeningError, normalize_repository_path

BenchmarkMode = Literal["deterministic", "one-model", "council"]
CASE_SCHEMA = "sergeant.blind-benchmark.case.v1"
RESULT_SCHEMA = "sergeant.blind-benchmark.result.v1"
_ALLOWED_SEVERITIES = {"blocker", "major", "minor"}
class ReviewBenchmarkError(ValueError):
    """Raised when a blind benchmark case or mode is invalid."""


@dataclass(frozen=True)
class FindingMatch:
    expected_id: str
    matched: bool
    score: float
    candidate: dict[str, Any] | None
    category_correct: bool
    severity_correct: bool
    path_correct: bool
    line_correct: bool | None
    root_cause_correct: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    title: str
    mode: BenchmarkMode
    expected_verdict: str
    actual_verdict: str
    verdict_correct: bool
    expected_count: int
    prediction_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    precision: float
    recall: float
    f1: float
    severity_accuracy: float | None
    path_accuracy: float | None
    line_accuracy: float | None
    root_cause_accuracy: float | None
    duplicate_rate: float
    finding_completeness: float | None
    duration_ms: float
    cpl_status: str
    model_call_count: int
    distinct_models: list[str]
    matches: list[FindingMatch]
    false_positive_candidates: list[dict[str, Any]]
    missed_expected_findings: list[dict[str, Any]]
    review_packet: dict[str, Any]

    def to_dict(self, *, include_packet: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["matches"] = [item.to_dict() for item in self.matches]
        if not include_packet:
            payload.pop("review_packet", None)
        return payload


def _tokens(value: object) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "this", "that", "should", "may", "into", "when", "before"}
    return {
        word
        for word in re.findall(r"[a-z0-9_]+", str(value or "").lower())
        if len(word) > 2 and word not in stop
    }


def _normalize_finding(item: dict[str, Any], source: str) -> dict[str, Any] | None:
    severity = str(item.get("severity") or "").lower()
    if severity not in _ALLOWED_SEVERITIES:
        return None
    start = item.get("line_start") or item.get("line")
    end = item.get("line_end") or start
    confidence = item.get("confidence")
    return {
        "source": source,
        "category": str(item.get("capability") or item.get("category") or "other").lower(),
        "severity": severity,
        "message": str(item.get("message") or "").strip(),
        "evidence": str(item.get("evidence") or "").strip(),
        "path": str(item.get("path") or "").strip() or None,
        "line_start": start if isinstance(start, int) else None,
        "line_end": end if isinstance(end, int) else None,
        "root_cause": str(item.get("root_cause") or "").strip() or None,
        "why_it_matters": str(item.get("why_it_matters") or "").strip(),
        "trigger": str(item.get("trigger") or "").strip(),
        "consequence": str(item.get("consequence") or "").strip(),
        "safer_alternative": str(item.get("safer_alternative") or "").strip(),
        "verification_test": str(item.get("verification_test") or "").strip(),
        "confidence": float(confidence) if confidence is not None else 0.0,
    }


def _bucket(packet: dict[str, Any], section: str) -> list[dict[str, Any]]:
    payload = packet.get(section, {})
    if not isinstance(payload, dict):
        return []
    rows: list[dict[str, Any]] = []
    for name in ("blocking_findings", "major_findings", "minor_findings"):
        values = payload.get(name, [])
        if isinstance(values, list):
            rows.extend(item for item in values if isinstance(item, dict))
    return rows


def extract_predictions(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Return unique actionable predictions and the count of valid predictions.

    The second value excludes notes and unrecognized severities. Duplicate rate
    therefore measures duplicate-key collisions among valid findings only.
    """

    raw: list[tuple[str, dict[str, Any]]] = []
    formation = packet.get("officer_council")
    if isinstance(formation, dict):
        # Benchmark the Judge ledger, not pre-adjudication scanner votes.  Minor
        # advisories remain measurable findings, while generic risk triggers
        # and rejected claims cannot inflate quality scores or verdicts.
        raw.extend(
            ("officer-council", item)
            for item in formation.get("admitted_findings", [])
            if isinstance(item, dict)
        )
        raw.extend(
            ("officer-council", item)
            for item in formation.get("advisory_findings", [])
            if isinstance(item, dict)
            and item.get("admission") == "advisory"
        )
    else:
        # Backward-compatible packets created before the permanent-officer
        # formation retain the historical extraction behavior.
        raw.extend(("repository", item) for item in _bucket(packet, "repository_review"))
        raw.extend(("diff", item) for item in _bucket(packet, "diff_review"))
        capability = packet.get("capability_review", {})
        if isinstance(capability, dict):
            raw.extend(("capability", item) for item in capability.get("findings", []) if isinstance(item, dict))
        cpl = packet.get("cpl_review", packet.get("semantic_review", {}))
        if isinstance(cpl, dict):
            cpl_findings = cpl.get("actionable_findings")
            if not isinstance(cpl_findings, list):
                cpl_findings = cpl.get("findings", [])
            raw.extend(("cpl", item) for item in cpl_findings if isinstance(item, dict))

    unique: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    valid_count = 0
    for source, item in raw:
        finding = _normalize_finding(item, source)
        if finding is None:
            continue
        valid_count += 1
        key = (finding["category"], finding["message"].lower(), finding["path"], finding["line_start"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique, valid_count


def _path_ok(expected: dict[str, Any], candidate: dict[str, Any]) -> bool:
    paths = [str(item) for item in expected.get("paths", [])]
    return not paths or candidate.get("path") in paths


def _line_ok(expected: dict[str, Any], candidate: dict[str, Any]) -> bool | None:
    start = expected.get("line_start")
    if not isinstance(start, int):
        return None
    end = expected.get("line_end") or start
    candidate_start = candidate.get("line_start")
    candidate_end = candidate.get("line_end") or candidate_start
    return bool(isinstance(candidate_start, int) and candidate_start <= end and candidate_end >= start)


def _score(expected: dict[str, Any], candidate: dict[str, Any]) -> float:
    category = str(expected.get("category") or "").lower()
    aliases = {category, *[str(item).lower() for item in expected.get("category_aliases", [])]}
    category_score = 1.0 if candidate.get("category") in aliases else 0.0
    path_score = 1.0 if _path_ok(expected, candidate) else 0.0
    keywords = {str(item).lower() for item in expected.get("keywords", [])}
    text = " ".join(str(candidate.get(key) or "") for key in ("message", "evidence", "root_cause"))
    keyword_score = len(keywords & _tokens(text)) / max(1, len(keywords))
    severity_score = 1.0 if candidate.get("severity") == str(expected.get("severity") or "").lower() else 0.0
    root = str(expected.get("root_cause") or "")
    root_score = 1.0 if root and candidate.get("root_cause") == root else 0.0
    return round(
        category_score * 0.28
        + path_score * 0.27
        + keyword_score * 0.30
        + severity_score * 0.10
        + root_score * 0.05,
        3,
    )


def _matches(
    expected: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float,
) -> tuple[list[FindingMatch], set[int]]:
    available = set(range(len(predictions)))
    output: list[FindingMatch] = []
    used: set[int] = set()
    for item in expected:
        scored = sorted(((_score(item, predictions[index]), index) for index in available), reverse=True)
        score, index = scored[0] if scored else (0.0, -1)
        matched = index >= 0 and score >= threshold
        candidate = predictions[index] if matched else None
        if matched:
            available.remove(index)
            used.add(index)
        aliases = {
            str(item.get("category") or "").lower(),
            *[str(value).lower() for value in item.get("category_aliases", [])],
        }
        root = str(item.get("root_cause") or "")
        output.append(
            FindingMatch(
                expected_id=str(item.get("id") or "expected"),
                matched=matched,
                score=score,
                candidate=candidate,
                category_correct=bool(candidate and candidate.get("category") in aliases),
                severity_correct=bool(
                    candidate and candidate.get("severity") == str(item.get("severity") or "").lower()
                ),
                path_correct=bool(candidate and _path_ok(item, candidate)),
                line_correct=(
                    _line_ok(item, candidate)
                    if candidate
                    else (False if isinstance(item.get("line_start"), int) else None)
                ),
                root_cause_correct=(
                    bool(candidate and candidate.get("root_cause") == root) if root else None
                ),
            )
        )
    return output, used


def _accuracy(values: Iterable[bool | None]) -> float | None:
    rows = [value for value in values if value is not None]
    return round(sum(bool(value) for value in rows) / len(rows), 3) if rows else None


def _completeness(predictions: list[dict[str, Any]]) -> float | None:
    if not predictions:
        return None
    scores = []
    for item in predictions:
        checks = [
            bool(item.get("message")),
            bool(item.get("evidence")),
            bool(item.get("path")) or item.get("category") == "test_impact",
            bool(item.get("why_it_matters")) or item.get("source") != "cpl",
            bool(item.get("safer_alternative")) or item.get("source") != "cpl",
        ]
        scores.append(sum(checks) / len(checks))
    return round(sum(scores) / len(scores), 3)


def validate_case(payload: dict[str, Any], path: Path | None = None) -> None:
    label = str(path or "case")
    if payload.get("schema_version") != CASE_SCHEMA:
        raise ReviewBenchmarkError(f"{label} must use schema_version {CASE_SCHEMA!r}.")
    if not str(payload.get("id") or "").strip():
        raise ReviewBenchmarkError(f"{label} is missing id.")
    files = payload.get("files")
    changed = payload.get("changed_files")
    expected = payload.get("expected_findings")
    if not isinstance(files, list) or not files:
        raise ReviewBenchmarkError(f"{label} requires a non-empty files list.")
    if not isinstance(changed, list) or not changed:
        raise ReviewBenchmarkError(f"{label} requires a non-empty changed_files list.")
    if not isinstance(expected, list):
        raise ReviewBenchmarkError(f"{label} expected_findings must be a list.")
    file_paths = {str(item.get("path") or "") for item in files if isinstance(item, dict)}
    if not set(map(str, changed)).issubset(file_paths):
        raise ReviewBenchmarkError(f"{label} changed_files must exist in files.")
    for item in expected:
        if not isinstance(item, dict) or not all(item.get(key) for key in ("id", "category", "severity")):
            raise ReviewBenchmarkError(f"{label} has an invalid expected finding.")


def load_cases(suite: str | Path) -> list[tuple[Path, dict[str, Any]]]:
    location = Path(suite)
    paths = sorted(location.glob("*.json")) if location.is_dir() else [location]
    cases: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ReviewBenchmarkError(f"{path} must contain a JSON object.")
        validate_case(payload, path)
        cases.append((path, payload))
    if not cases:
        raise ReviewBenchmarkError(f"No benchmark cases found under {location}.")
    return cases


def _materialize(payload: dict[str, Any], root: Path) -> None:
    for item in payload["files"]:
        relative = str(item.get("path") or "")
        try:
            safe = normalize_repository_path(root, relative)
        except HardeningError as error:
            raise ReviewBenchmarkError(f"Unsafe benchmark file path {relative!r}: {error}") from error
        destination = root / safe
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(str(item.get("content") or ""), encoding="utf-8")


@contextmanager
def _mode_environment(mode: BenchmarkMode) -> Iterator[None]:
    names = {
        "SERGEANT_CPL_ENABLED",
        "SERGEANT_LLM_ENABLED",
        "SERGEANT_CPL_POLICY",
        "SERGEANT_LLM_POLICY",
        "SERGEANT_CPL_MAX_COUNCIL_MEMBERS",
        "SERGEANT_CPL_MAX_ROUNDS",
    }
    previous = {name: os.environ.get(name) for name in names}
    try:
        if mode == "deterministic":
            os.environ["SERGEANT_CPL_ENABLED"] = "false"
            os.environ["SERGEANT_CPL_POLICY"] = "disabled"
        else:
            os.environ["SERGEANT_CPL_ENABLED"] = "true"
            os.environ["SERGEANT_CPL_POLICY"] = "required"
            os.environ["SERGEANT_CPL_MAX_COUNCIL_MEMBERS"] = (
                "1" if mode == "one-model" else os.getenv("SERGEANT_CPL_MAX_COUNCIL_MEMBERS", "5")
            )
            os.environ["SERGEANT_CPL_MAX_ROUNDS"] = (
                "1" if mode == "one-model" else os.getenv("SERGEANT_CPL_MAX_ROUNDS", "3")
            )
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _verdict(packet: dict[str, Any]) -> str:
    value = packet.get("verdict", {})
    return str(value.get("verdict") or "UNKNOWN") if isinstance(value, dict) else "UNKNOWN"


def run_case(
    payload: dict[str, Any],
    *,
    mode: BenchmarkMode,
    match_threshold: float = 0.55,
) -> BenchmarkCaseResult:
    validate_case(payload)
    with tempfile.TemporaryDirectory(prefix="sergeant-blind-bench-") as temp:
        root = Path(temp)
        _materialize(payload, root)
        started = time.monotonic()
        with _mode_environment(mode):
            packet = run_independent_pr_review(root, changed_files=list(map(str, payload["changed_files"])))
        duration = round((time.monotonic() - started) * 1000, 2)

    predictions, valid_prediction_count = extract_predictions(packet)
    expected = [dict(item) for item in payload.get("expected_findings", [])]
    matches, used = _matches(expected, predictions, match_threshold)
    true_positives = sum(item.matched for item in matches)
    false_positives = len(predictions) - len(used)
    false_negatives = len(expected) - true_positives
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 1.0
    )
    recall = true_positives / len(expected) if expected else (1.0 if not predictions else 0.0)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    duplicate_count = max(0, valid_prediction_count - len(predictions))
    cpl = packet.get("cpl_review", {}) if isinstance(packet.get("cpl_review"), dict) else {}
    passes = [item for item in cpl.get("passes", []) if isinstance(item, dict)]
    models = sorted({str(item.get("model")) for item in passes if item.get("model")})
    actual = _verdict(packet)
    expected_verdict = str(payload.get("expected_verdict") or "UNKNOWN")
    return BenchmarkCaseResult(
        case_id=str(payload["id"]),
        title=str(payload.get("title") or payload["id"]),
        mode=mode,
        expected_verdict=expected_verdict,
        actual_verdict=actual,
        verdict_correct=actual == expected_verdict,
        expected_count=len(expected),
        prediction_count=len(predictions),
        true_positive_count=true_positives,
        false_positive_count=false_positives,
        false_negative_count=false_negatives,
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        severity_accuracy=_accuracy(item.severity_correct for item in matches if item.matched),
        path_accuracy=_accuracy(item.path_correct for item in matches if item.matched),
        line_accuracy=_accuracy(item.line_correct for item in matches if item.matched),
        root_cause_accuracy=_accuracy(item.root_cause_correct for item in matches if item.matched),
        duplicate_rate=round(duplicate_count / max(1, valid_prediction_count), 3),
        finding_completeness=_completeness(predictions),
        duration_ms=duration,
        cpl_status=str(cpl.get("status") or "missing"),
        model_call_count=len(passes),
        distinct_models=models,
        matches=matches,
        false_positive_candidates=[item for index, item in enumerate(predictions) if index not in used],
        missed_expected_findings=[item for item, match in zip(expected, matches) if not match.matched],
        review_packet=packet,
    )


def _mean(values: Iterable[float | None]) -> float | None:
    rows = [float(item) for item in values if item is not None]
    return round(sum(rows) / len(rows), 3) if rows else None


def run_blind_benchmark(
    suite: str | Path,
    *,
    mode: BenchmarkMode = "deterministic",
    match_threshold: float = 0.55,
    minimum_precision: float = 0.6,
    minimum_recall: float = 0.75,
    require_route: bool = False,
    include_packets: bool = False,
) -> dict[str, Any]:
    if mode not in {"deterministic", "one-model", "council"}:
        raise ReviewBenchmarkError(f"Unsupported benchmark mode: {mode!r}")
    results = [
        run_case(payload, mode=mode, match_threshold=match_threshold)
        for _, payload in load_cases(suite)
    ]
    expected_total = sum(item.expected_count for item in results)
    true_positives = sum(item.true_positive_count for item in results)
    false_positives = sum(item.false_positive_count for item in results)
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 1.0
    )
    recall = true_positives / expected_total if expected_total else (1.0 if false_positives == 0 else 0.0)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    route_ready = mode == "deterministic" or all(
        item.cpl_status in {"completed", "completed_with_warnings"} for item in results
    )
    passed = (
        precision >= minimum_precision
        and recall >= minimum_recall
        and all(item.verdict_correct for item in results)
    )
    if require_route and not route_ready:
        passed = False
    return {
        "schema_version": RESULT_SCHEMA,
        "blind": True,
        "mode": mode,
        "case_count": len(results),
        "expected_finding_count": expected_total,
        "true_positive_count": true_positives,
        "false_positive_count": false_positives,
        "false_negative_count": sum(item.false_negative_count for item in results),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "severity_accuracy": _mean(item.severity_accuracy for item in results),
        "path_accuracy": _mean(item.path_accuracy for item in results),
        "line_accuracy": _mean(item.line_accuracy for item in results),
        "root_cause_accuracy": _mean(item.root_cause_accuracy for item in results),
        "verdict_accuracy": round(
            sum(item.verdict_correct for item in results) / max(1, len(results)),
            3,
        ),
        "duplicate_rate": _mean(item.duplicate_rate for item in results),
        "finding_completeness": _mean(item.finding_completeness for item in results),
        "duration_ms": round(sum(item.duration_ms for item in results), 2),
        "model_call_count": sum(item.model_call_count for item in results),
        "distinct_models": sorted({model for item in results for model in item.distinct_models}),
        "route_ready": route_ready,
        "usage": {
            "available": False,
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost": None,
        },
        "thresholds": {
            "match": match_threshold,
            "minimum_precision": minimum_precision,
            "minimum_recall": minimum_recall,
            "require_route": require_route,
        },
        "passed": passed,
        "cases": [item.to_dict(include_packet=include_packets) for item in results],
        "rule": "Expected answers are loaded only after review returns; existing comments and fixture prose are not review input.",
    }


def default_suite_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "review-benchmarks" / "blind",
        Path(sysconfig.get_path("data")) / "share" / "sergeant" / "review-benchmarks" / "blind",
    ]
    return next((item for item in candidates if item.is_dir()), candidates[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sergeant-bench",
        description="Run Sergeant's blind review-quality benchmark.",
    )
    parser.add_argument("suite", nargs="?", default=str(default_suite_path()))
    parser.add_argument("--mode", choices=["deterministic", "one-model", "council"], default="deterministic")
    parser.add_argument("--match-threshold", type=float, default=0.55)
    parser.add_argument("--minimum-precision", type=float, default=0.6)
    parser.add_argument("--minimum-recall", type=float, default=0.75)
    parser.add_argument("--require-route", action="store_true")
    parser.add_argument("--include-packets", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_blind_benchmark(
        args.suite,
        mode=args.mode,
        match_threshold=args.match_threshold,
        minimum_precision=args.minimum_precision,
        minimum_recall=args.minimum_recall,
        require_route=args.require_route,
        include_packets=args.include_packets,
    )
    text = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if payload["passed"] or args.no_fail else 2


if __name__ == "__main__":
    raise SystemExit(main())
