"""Evidence-first side-by-side comparison of Sergeant and an external reviewer.

The comparator never declares a winner from comment volume or heuristic
matching. It preserves both reports, matches likely-equivalent findings, and
requires explicit repository-backed adjudication before quality claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .github_live_fetch import GitHubFetchError, fetch_pr_comments_live
from .review_ingestion import ExternalReviewComment, load_external_comments

COMPARISON_SCHEMA = "sergeant.reviewer-comparison.v1"
FindingSeverity = Literal["blocker", "major", "minor"]
DecisionStatus = Literal["confirmed", "suggestion", "false_positive", "duplicate", "uncertain"]
_ALLOWED_SEVERITIES = {"blocker", "major", "minor"}
_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.I)
_HEADING_RE = re.compile(r"^\s*(?:#+\s*)?(?:\[[^]]+\]\s*)?(.*)$")
_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
_METADATA_CATEGORY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("security",)),
    ("correctness", ("functional correctness", "correctness")),
    ("concurrency", ("concurrency",)),
    ("performance", ("performance",)),
    ("api_contract", ("api contract",)),
    ("architecture", ("architecture",)),
    ("testing", ("testing", "tests")),
    ("documentation", ("documentation",)),
)
_CATEGORY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("security", "auth", "authorization", "credential", "secret", "injection", "traversal")),
    ("correctness", ("incorrect", "bug", "broken", "wrong", "exception", "failure")),
    ("concurrency", ("race", "concurrent", "async", "thread", "lock")),
    ("performance", ("performance", "slow", "latency", "complexity", "memory")),
    ("api_contract", ("api", "contract", "schema", "compatibility", "route")),
    ("architecture", ("architecture", "boundary", "coupling", "dependency", "layer")),
    ("testing", ("test", "coverage", "regression proof")),
    ("documentation", ("documentation", "readme", "docstring")),
)


class ReviewerComparisonError(ValueError):
    """Raised when comparison evidence is invalid or incomplete."""


@dataclass(frozen=True)
class ComparisonFinding:
    finding_id: str
    reviewer: str
    severity: FindingSeverity
    category: str
    message: str
    evidence: str
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    root_cause: str | None = None
    url: str | None = None
    source_id: str | None = None
    source_layer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FindingPair:
    sergeant: ComparisonFinding
    reference: ComparisonFinding
    match_score: float
    path_match: bool
    line_match: bool | None
    category_match: bool
    token_overlap: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sergeant": self.sergeant.to_dict(),
            "reference": self.reference.to_dict(),
            "match_score": self.match_score,
            "path_match": self.path_match,
            "line_match": self.line_match,
            "category_match": self.category_match,
            "token_overlap": self.token_overlap,
        }


def _text(value: object) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *values: object) -> str:
    material = "\x1f".join(_text(value) for value in values)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _marker_pattern(marker: str) -> re.Pattern[str]:
    escaped = re.escape(marker)
    prefix = r"(?<![A-Za-z0-9])" if marker and marker[0].isalnum() else ""
    suffix = r"(?![A-Za-z0-9])" if marker and marker[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.I)


def _contains_marker(text: str, markers: Iterable[str]) -> bool:
    return any(_marker_pattern(marker).search(text) for marker in markers)


def _tokens(*values: object) -> set[str]:
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "into", "when",
        "should", "could", "would", "may", "might", "file", "line", "code",
    }
    return {
        token.lower()
        for value in values
        for token in _TOKEN_RE.findall(_text(value))
        if len(token) > 2 and token.lower() not in stop
    }


def _coderabbit_header(body: str) -> tuple[FindingSeverity | None, str | None, bool]:
    """Read a CodeRabbit-style metadata banner using bounded markers."""

    lines = [line.strip() for line in body.splitlines()[:4] if line.strip()]
    header = "\n".join(lines)
    recognized = bool(
        any("|" in line for line in lines)
        and (
            _contains_marker(header, ("minor", "major", "critical", "nitpick"))
            or any(symbol in header for symbol in ("🔵", "🟡", "🟠", "🔴"))
        )
    )
    if not recognized:
        return None, None, False

    if _contains_marker(header, ("nitpick",)) or "🔵" in header:
        severity: FindingSeverity | None = None
    elif _contains_marker(header, ("critical", "blocker")) or "🔴" in header:
        severity = "blocker"
    elif _contains_marker(header, ("major",)) or "🟠" in header:
        severity = "major"
    else:
        severity = "minor"

    category = next(
        (name for name, markers in _METADATA_CATEGORY_MARKERS if _contains_marker(header, markers)),
        None,
    )
    return severity, category, True


def _metadata_line(line: str) -> bool:
    severity, category, recognized = _coderabbit_header(line)
    return recognized and (severity is not None or category is not None or _contains_marker(line, ("nitpick",)))


def _first_message_line(body: str) -> str:
    """Return the actual issue title rather than reviewer metadata or HTML."""

    fallback: str | None = None
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("<!--", "<details", "</details", "```", ">")):
            continue
        if _metadata_line(line):
            continue
        bold = _BOLD_RE.match(line)
        if bold:
            return bold.group(1).strip()[:400]
        if line.startswith("<summary>"):
            continue
        match = _HEADING_RE.match(line)
        value = _text(match.group(1) if match else line).strip("_*")
        value = re.sub(
            r"^(?:potential issue|bug|issue|warning|suggestion|nitpick)\s*[:\-]\s*",
            "",
            value,
            flags=re.I,
        )
        if value and fallback is None:
            fallback = value[:400]
    return fallback or body.strip()[:400] or "External reviewer finding"


def _infer_severity(body: str) -> FindingSeverity | None:
    explicit, _, recognized = _coderabbit_header(body)
    if recognized:
        return explicit
    lowered = body.lower()
    if _contains_marker(lowered, ("nitpick", "nit:", "style-only", "style only")):
        return None
    if _contains_marker(lowered, ("critical", "blocker", "p0", "severity: critical")):
        return "blocker"
    if _contains_marker(lowered, ("major", "high severity", "security vulnerability", "potential issue")):
        return "major"
    return "minor"


def _infer_category(body: str, tags: Iterable[str] = ()) -> str:
    _, explicit, recognized = _coderabbit_header(body)
    if recognized and explicit:
        return explicit
    text = " ".join([body, *tags]).lower()
    return next((name for name, markers in _CATEGORY_MARKERS if _contains_marker(text, markers)), "other")


def _normalized_author(value: object) -> str:
    return _text(value).lower().removesuffix("[bot]").removesuffix("-bot")


def _bucket_rows(packet: dict[str, Any], section: str) -> list[dict[str, Any]]:
    value = packet.get(section, {})
    if not isinstance(value, dict):
        return []
    rows: list[dict[str, Any]] = []
    for bucket in ("blocking_findings", "major_findings", "minor_findings"):
        items = value.get(bucket, [])
        if isinstance(items, list):
            rows.extend(item for item in items if isinstance(item, dict))
    return rows


def _sergeant_sources(packet: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    sources: list[tuple[str, dict[str, Any]]] = []
    intelligence = packet.get("review_intelligence", {})
    ranked = intelligence.get("ranked_findings", []) if isinstance(intelligence, dict) else []
    if isinstance(ranked, list) and ranked:
        sources.extend(("review_intelligence", item) for item in ranked if isinstance(item, dict))
    else:
        capability = packet.get("capability_review", {})
        findings = capability.get("findings", []) if isinstance(capability, dict) else []
        if isinstance(findings, list):
            sources.extend(("capability_review", item) for item in findings if isinstance(item, dict))
    sources.extend(("diff_review", item) for item in _bucket_rows(packet, "diff_review"))
    sources.extend(("repository_review", item) for item in _bucket_rows(packet, "repository_review"))
    cpl = packet.get("cpl_review", {})
    cpl_findings = cpl.get("findings", []) if isinstance(cpl, dict) else []
    if isinstance(cpl_findings, list):
        sources.extend(("cpl_review", item) for item in cpl_findings if isinstance(item, dict))
    return sources


def extract_sergeant_findings(packet: dict[str, Any], reviewer_name: str = "Sergeant") -> list[ComparisonFinding]:
    """Extract actionable findings from every Sergeant verdict-bearing layer."""

    findings: list[ComparisonFinding] = []
    seen: set[tuple[object, ...]] = set()
    for source, row in _sergeant_sources(packet if isinstance(packet, dict) else {}):
        severity = _text(row.get("severity")).lower()
        if severity not in _ALLOWED_SEVERITIES:
            continue
        challenge = _text(row.get("challenge_result"))
        if severity in {"blocker", "major"} and challenge and not challenge.startswith("survived:"):
            continue
        category = _text(row.get("capability") or row.get("category")) or "other"
        message = _text(row.get("message")) or "Sergeant finding"
        evidence = _text(row.get("evidence"))
        path = _text(row.get("path")) or None
        line_start = row.get("line_start") or row.get("line")
        line_end = row.get("line_end") or line_start
        key = (category, message.lower(), path, line_start)
        if key in seen:
            continue
        seen.add(key)
        finding_id = _text(row.get("finding_id")) or _stable_id("sergeant", source, category, path, line_start, message)
        findings.append(ComparisonFinding(
            finding_id=finding_id,
            reviewer=reviewer_name,
            severity=severity,  # type: ignore[arg-type]
            category=category,
            message=message,
            evidence=evidence,
            path=path,
            line_start=int(line_start) if isinstance(line_start, int) else None,
            line_end=int(line_end) if isinstance(line_end, int) else None,
            root_cause=_text(row.get("root_cause")) or None,
            source_id=_text(row.get("evidence_ref")) or None,
            source_layer=source,
        ))
    return findings


def extract_external_findings(comments: Iterable[ExternalReviewComment], reviewer_name: str) -> list[ComparisonFinding]:
    """Normalize actionable external comments without counting summaries/nitpicks."""

    findings: list[ComparisonFinding] = []
    seen: set[tuple[object, ...]] = set()
    for comment in comments:
        body = comment.body.strip()
        if not body:
            continue
        severity = _infer_severity(body)
        if severity is None:
            continue
        if not comment.path and not _contains_marker(
            body.lower(), ("potential issue", "bug", "critical", "blocker", "security vulnerability")
        ):
            continue
        message = _first_message_line(body)
        category = _infer_category(body, comment.tags)
        key = (message.lower(), comment.path, comment.line, category)
        if key in seen:
            continue
        seen.add(key)
        stable_source = comment.url or f"{comment.author}|{comment.path}|{comment.line}|{body}"
        findings.append(ComparisonFinding(
            finding_id=_stable_id("reference", stable_source),
            reviewer=reviewer_name,
            severity=severity,
            category=category,
            message=message,
            evidence=body[:4000],
            path=comment.path,
            line_start=comment.line,
            line_end=comment.line,
            url=comment.url,
            source_id=comment.url or _text(comment.author) or None,
            source_layer="external_review",
        ))
    return findings


def load_live_external_comments(
    repository: str,
    pr_number: int,
    *,
    author: str,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    allowed_hosts: Iterable[str] = (),
    allow_private: bool = False,
    expected_head_sha: str | None = None,
) -> tuple[list[ExternalReviewComment], dict[str, Any]]:
    """Fetch one reviewer's comments while enforcing a frozen pull-request head."""

    result = fetch_pr_comments_live(
        repository,
        pr_number,
        token=token,
        base_url=base_url,
        allowed_hosts=allowed_hosts,
        allow_private=allow_private,
    )
    head = result.pull_request.get("head", {})
    actual_head = head.get("sha") if isinstance(head, dict) else None
    if expected_head_sha and actual_head != expected_head_sha:
        raise ReviewerComparisonError(f"PR head changed during comparison: expected {expected_head_sha}, got {actual_head}.")

    wanted = _normalized_author(author)
    comments: list[ExternalReviewComment] = []
    stale_comment_count = 0
    for item in result.all_comments:
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        login = _text(user.get("login"))
        if _normalized_author(login) != wanted:
            continue
        commit_id = _text(item.get("commit_id"))
        if expected_head_sha and commit_id and commit_id != expected_head_sha:
            stale_comment_count += 1
            continue
        comments.append(ExternalReviewComment(
            source="live-github-review",
            body=_text(item.get("body")),
            repository=repository,
            pr_number=pr_number,
            path=_text(item.get("path")) or None,
            line=item.get("line") if isinstance(item.get("line"), int) else None,
            author=login or author,
            url=_text(item.get("html_url")) or None,
        ))
    metadata = {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": actual_head,
        "reference_author": author,
        "fetched_comment_count": len(result.all_comments),
        "matched_author_comment_count": len(comments),
        "stale_comment_count": stale_comment_count,
        "proof": result.proof_dict(),
    }
    return comments, metadata


def _path_match(left: ComparisonFinding, right: ComparisonFinding) -> bool:
    return bool(left.path and right.path and left.path.replace("\\", "/") == right.path.replace("\\", "/"))


def _line_match(left: ComparisonFinding, right: ComparisonFinding) -> bool | None:
    if left.line_start is None or right.line_start is None:
        return None
    left_end = left.line_end or left.line_start
    right_end = right.line_end or right.line_start
    return left.line_start <= right_end + 3 and right.line_start <= left_end + 3


def _token_overlap(left: ComparisonFinding, right: ComparisonFinding) -> float:
    left_tokens = _tokens(left.message, left.evidence, left.root_cause)
    right_tokens = _tokens(right.message, right.evidence, right.root_cause)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def finding_match_score(left: ComparisonFinding, right: ComparisonFinding) -> tuple[float, bool, bool | None, bool, float]:
    path_match = _path_match(left, right)
    line_match = _line_match(left, right)
    category_match = left.category == right.category or {left.category, right.category} <= {"security", "security_taint", "data_flow"}
    overlap = _token_overlap(left, right)
    score = overlap * 0.40 + (0.35 if path_match else 0) + (0.15 if line_match is True else 0) + (0.10 if category_match else 0)
    return round(min(score, 1.0), 3), path_match, line_match, category_match, round(overlap, 3)


def match_findings(
    sergeant: list[ComparisonFinding],
    reference: list[ComparisonFinding],
    *,
    threshold: float = 0.45,
) -> tuple[list[FindingPair], list[ComparisonFinding], list[ComparisonFinding]]:
    """Greedily match likely-equivalent findings and preserve both unique sets."""

    available = set(range(len(reference)))
    pairs: list[FindingPair] = []
    unmatched_sergeant: list[ComparisonFinding] = []
    for finding in sergeant:
        scored = sorted(
            ((finding_match_score(finding, reference[index]), index) for index in available),
            key=lambda item: item[0][0],
            reverse=True,
        )
        if not scored or scored[0][0][0] < threshold:
            unmatched_sergeant.append(finding)
            continue
        (score, path_match, line_match, category_match, overlap), index = scored[0]
        available.remove(index)
        pairs.append(FindingPair(
            sergeant=finding,
            reference=reference[index],
            match_score=score,
            path_match=path_match,
            line_match=line_match,
            category_match=category_match,
            token_overlap=overlap,
        ))
    return pairs, unmatched_sergeant, [reference[index] for index in sorted(available)]


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReviewerComparisonError(f"{path} must contain a JSON object.")
    return payload


def _load_decisions(path: str | Path | None) -> dict[tuple[str, str], DecisionStatus]:
    if path is None:
        return {}
    payload = _load_json(path)
    rows = payload.get("decisions", [])
    if not isinstance(rows, list):
        raise ReviewerComparisonError("adjudication decisions must be a list.")
    allowed = {"confirmed", "suggestion", "false_positive", "duplicate", "uncertain"}
    decisions: dict[tuple[str, str], DecisionStatus] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        reviewer = _text(item.get("reviewer"))
        finding_id = _text(item.get("finding_id"))
        status = _text(item.get("status")).lower()
        if reviewer and finding_id and status in allowed:
            decisions[(reviewer, finding_id)] = status  # type: ignore[assignment]
    return decisions


def _adjudication_summary(findings: Iterable[ComparisonFinding], decisions: dict[tuple[str, str], DecisionStatus]) -> dict[str, Any]:
    rows = list(findings)
    decided = [decisions[(item.reviewer, item.finding_id)] for item in rows if (item.reviewer, item.finding_id) in decisions]
    counts = {status: decided.count(status) for status in ("confirmed", "suggestion", "false_positive", "duplicate", "uncertain")}
    denominator = counts["confirmed"] + counts["false_positive"]
    return {
        "finding_count": len(rows),
        "adjudicated_count": len(decided),
        "complete": len(decided) == len(rows),
        "counts": counts,
        "verified_precision": round(counts["confirmed"] / denominator, 3) if denominator else None,
    }


def compare_reviewer_reports(
    sergeant_packet: dict[str, Any],
    reference_comments: Iterable[ExternalReviewComment],
    *,
    reference_name: str,
    match_threshold: float = 0.45,
    adjudication_file: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a side-by-side report without inventing ground truth or a winner."""

    sergeant = extract_sergeant_findings(sergeant_packet)
    reference = extract_external_findings(reference_comments, reference_name)
    shared, sergeant_only, reference_only = match_findings(sergeant, reference, threshold=match_threshold)
    decisions = _load_decisions(adjudication_file)
    sergeant_summary = _adjudication_summary(sergeant, decisions)
    reference_summary = _adjudication_summary(reference, decisions)
    adjudication_complete = sergeant_summary["complete"] and reference_summary["complete"] and bool(sergeant or reference)
    overlap_denominator = max(1, min(len(sergeant), len(reference)))
    return {
        "schema_version": COMPARISON_SCHEMA,
        "comparison_kind": "side-by-side-evidence",
        "reference_name": reference_name,
        "metadata": metadata or {},
        "match_threshold": match_threshold,
        "counts": {
            "sergeant": len(sergeant),
            "reference": len(reference),
            "shared": len(shared),
            "sergeant_only": len(sergeant_only),
            "reference_only": len(reference_only),
        },
        "overlap_rate": round(len(shared) / overlap_denominator, 3),
        "shared_findings": [pair.to_dict() for pair in shared],
        "sergeant_only": [finding.to_dict() for finding in sergeant_only],
        "reference_only": [finding.to_dict() for finding in reference_only],
        "adjudication": {
            "provided": bool(decisions),
            "complete": adjudication_complete,
            "sergeant": sergeant_summary,
            "reference": reference_summary,
        },
        "winner": None,
        "winner_rule": "No winner is declared from overlap, comment volume, or heuristic matching. Confirmed defects, false positives, and missed defects require Judge/human verification.",
        "caveats": [
            "Shared means the reports appear to describe the same issue; it does not prove validity.",
            "Unique findings require repository verification before being scored as reviewer advantage.",
            "Recall is undefined until the complete verified defect set is known.",
        ],
    }


def _cell(finding: dict[str, Any]) -> str:
    location = _text(finding.get("path"))
    if finding.get("line_start"):
        location = f"{location}:{finding['line_start']}" if location else f"line {finding['line_start']}"
    prefix = f"**{location}** — " if location else ""
    return (prefix + _text(finding.get("message"))).replace("|", "\\|")


def render_comparison_markdown(result: dict[str, Any]) -> str:
    counts = result.get("counts", {})
    reference_name = _text(result.get("reference_name")) or "Reference reviewer"
    lines = [
        "# Sergeant Reviewer Comparison", "",
        f"| Metric | Sergeant | {reference_name} |", "|---|---:|---:|",
        f"| Actionable findings | {counts.get('sergeant', 0)} | {counts.get('reference', 0)} |",
        f"| Shared findings | {counts.get('shared', 0)} | {counts.get('shared', 0)} |",
        f"| Unique findings | {counts.get('sergeant_only', 0)} | {counts.get('reference_only', 0)} |",
        "", "## Shared findings", "",
        f"| Sergeant | {reference_name} | Match |", "|---|---|---:|",
    ]
    shared = result.get("shared_findings", [])
    if shared:
        for pair in shared:
            lines.append(f"| {_cell(pair.get('sergeant', {}))} | {_cell(pair.get('reference', {}))} | {float(pair.get('match_score', 0)):.3f} |")
    else:
        lines.append("| _None matched_ | _None matched_ | — |")
    lines.extend(["", "## Unique findings", "", f"| Sergeant only | {reference_name} only |", "|---|---|"])
    left = list(result.get("sergeant_only", []))
    right = list(result.get("reference_only", []))
    if not left and not right:
        lines.append("| _None_ | _None_ |")
    else:
        for index in range(max(len(left), len(right))):
            lines.append(f"| {_cell(left[index]) if index < len(left) else ''} | {_cell(right[index]) if index < len(right) else ''} |")
    lines.extend([
        "", "## Adjudication boundary", "",
        "No winner is declared until each shared and unique finding is verified against repository evidence.",
        "Comment volume and textual overlap are not measures of reviewer quality.",
    ])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sergeant-compare", description="Compare Sergeant with an external reviewer side by side.")
    parser.add_argument("--sergeant-packet", required=True)
    reference = parser.add_mutually_exclusive_group(required=True)
    reference.add_argument("--reference-review")
    reference.add_argument("--live-repository")
    parser.add_argument("--live-pr", type=int)
    parser.add_argument("--reference-name", default="External reviewer")
    parser.add_argument("--reference-author")
    parser.add_argument("--expected-head-sha")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--base-url", default="https://api.github.com")
    parser.add_argument("--allowed-host", action="append", default=[])
    parser.add_argument("--allow-private", action="store_true")
    parser.add_argument("--match-threshold", type=float, default=0.45)
    parser.add_argument("--adjudication")
    parser.add_argument("--output")
    parser.add_argument("--markdown-output")
    parser.add_argument("--pretty", action="store_true")
    return parser


def _run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sergeant_packet = _load_json(args.sergeant_packet)
    metadata: dict[str, Any] = {}
    if args.reference_review:
        comments = load_external_comments(args.reference_review)
    else:
        if not args.live_pr or not args.reference_author:
            raise ReviewerComparisonError("--live-pr and --reference-author are required with --live-repository.")
        comments, metadata = load_live_external_comments(
            args.live_repository,
            args.live_pr,
            author=args.reference_author,
            token=os.getenv(args.token_env),
            base_url=args.base_url,
            allowed_hosts=args.allowed_host,
            allow_private=args.allow_private,
            expected_head_sha=args.expected_head_sha,
        )
    result = compare_reviewer_reports(
        sergeant_packet,
        comments,
        reference_name=args.reference_name,
        match_threshold=args.match_threshold,
        adjudication_file=args.adjudication,
        metadata=metadata,
    )
    text = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    markdown = render_comparison_markdown(result)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    if args.markdown_output:
        output = Path(args.markdown_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    print(text, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except (ReviewerComparisonError, GitHubFetchError, OSError, json.JSONDecodeError) as error:
        print(f"sergeant-compare: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
