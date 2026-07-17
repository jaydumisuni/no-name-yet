"""Evidence-grounded Cpl reasoning for Sergeant.

Cpl is Sergeant's native Corporal Specialist. The officer is provider-agnostic:
it decomposes review missions into specialist passes, rotates available models,
and contributes only findings tied back to supplied repository text.
Deterministic Sergeant evidence remains authoritative.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from .cpl_council import available_models, finding_root_cause, findings_match
from .cpl_reasoning import (
    CplAssignment,
    cpl_depth,
    plan_cpl_assignments,
    route_for_assignment,
    specialist_system_prompt,
)
from .llm_provider import (
    LLMProviderError,
    LLMRoute,
    LLMSettings,
    discover_route,
    invoke_json,
)

ALLOWED_VERDICTS = {"PASS", "NEEDS WORK", "BLOCK"}
ALLOWED_SEVERITIES = {"blocker", "major", "minor", "note"}
SEVERITY_RANK = {"note": 0, "minor": 1, "major": 2, "blocker": 3}

SYSTEM_PROMPT = """You are Cpl, Sergeant's Corporal Specialist reasoning officer.

Command relationship:
- Sergeant Main Review is the reviewer core and final engineering authority.
- You are Cpl, the provider-agnostic reasoning specialist serving Sergeant.
- A model is only one engine available to Cpl. Never present the model or gateway as the product identity.

Rules:
1. Review only the supplied changed-file excerpts and deterministic evidence.
2. Never invent files, lines, behavior, tests, or runtime results.
3. Every blocker or major finding must name a supplied path, a line range, and exact evidence grounded in that range.
4. Distinguish a demonstrated defect from a question, uncertainty, or missing proof.
5. Treat deterministic tests, runtime evidence, explicit contracts, and verified repository facts as stronger than speculation.
6. Look for interactions and second-order effects, not only isolated syntax.
7. Stay read-only. Do not propose automatic merge or direct repository writes.
8. Return JSON only. Do not wrap it in Markdown.

Return this shape:
{
  "verdict": "PASS | NEEDS WORK | BLOCK",
  "confidence": 0.0,
  "summary": "short evidence-based summary",
  "findings": [
    {
      "severity": "blocker | major | minor | note",
      "category": "correctness | security | architecture | concurrency | api_contract | tests | documentation | performance | maintainability | other",
      "path": "supplied/repository/path",
      "line_start": 1,
      "line_end": 1,
      "message": "specific problem",
      "evidence": "exact or near-exact text from the supplied line range",
      "why_it_matters": "concrete impact",
      "safer_alternative": "specific correction or proof"
    }
  ],
  "unanswered_questions": [],
  "coverage": {
    "files_reviewed": [],
    "areas": []
  }
}
"""


def _provider_failure_kind(error: LLMProviderError) -> str:
    """Return a credential-safe provider failure category for audit and retry policy."""

    message = str(error)
    status = re.search(r"\bHTTP\s+(\d{3})\b", message, flags=re.IGNORECASE)
    if status:
        return f"http_{status.group(1)}"
    lowered = message.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "unavailable" in lowered or "urlopen error" in lowered:
        return "unavailable"
    if "invalid json" in lowered or "non-json" in lowered:
        return "invalid_json"
    if "did not contain" in lowered or "unexpected json shape" in lowered:
        return "response_contract"
    return "provider_error"


def _provider_failure_summary(errors: list[LLMProviderError]) -> str:
    counts: dict[str, int] = {}
    for error in errors:
        kind = _provider_failure_kind(error)
        counts[kind] = counts.get(kind, 0) + 1
    return ", ".join(f"{kind}={counts[kind]}" for kind in sorted(counts))


def _invoke_json_with_failover(
    route: LLMRoute,
    *,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict[str, Any], LLMRoute, list[str]]:
    """Try each configured council model before declaring the officer pass failed."""

    failed_models: list[str] = []
    failures: list[LLMProviderError] = []
    for model in available_models(route):
        candidate = replace(route, model=model)
        try:
            return (
                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),
                candidate,
                failed_models,
            )
        except LLMProviderError as error:
            failed_models.append(model)
            failures.append(error)
    summary = _provider_failure_summary(failures)
    suffix = f" ({summary})" if summary else ""
    raise LLMProviderError(
        "No configured Cpl council model completed the required structured officer pass"
        f"{suffix}.",
        failed_models=failed_models,
    )


def _env(primary: str, legacy: str, default: str) -> str:
    value = os.getenv(primary)
    if value is not None:
        return value
    return os.getenv(legacy, default)


def _int_env_pair(primary: str, legacy: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(_env(primary, legacy, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def _safe_relative_file(root: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute():
        return None
    try:
        resolved_root = root.resolve()
        resolved = (resolved_root / candidate).resolve()
        if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            return None
    except OSError:
        return None
    return resolved


def _numbered_excerpt(text: str, *, max_chars: int) -> str:
    lines = text.splitlines()
    rendered: list[str] = []
    used = 0
    for index, line in enumerate(lines, start=1):
        row = f"{index:>6}: {line}\n"
        if used + len(row) > max_chars:
            rendered.append(f"... excerpt truncated after line {index - 1} ...\n")
            break
        rendered.append(row)
        used += len(row)
    return "".join(rendered)


def collect_changed_file_excerpts(
    root: str | Path,
    changed_files: list[str],
    *,
    max_total_chars: int | None = None,
    max_file_chars: int | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return raw text and numbered excerpts for safe changed files."""

    root_path = Path(root)
    total_limit = max_total_chars or _int_env_pair(
        "SERGEANT_CPL_MAX_INPUT_CHARS",
        "SERGEANT_LLM_MAX_INPUT_CHARS",
        120_000,
        minimum=8_000,
        maximum=1_000_000,
    )
    file_limit = max_file_chars or _int_env_pair(
        "SERGEANT_CPL_MAX_FILE_CHARS",
        "SERGEANT_LLM_MAX_FILE_CHARS",
        18_000,
        minimum=2_000,
        maximum=200_000,
    )
    raw: dict[str, str] = {}
    excerpts: dict[str, str] = {}
    remaining = total_limit

    for relative in dict.fromkeys(path.strip() for path in changed_files if path.strip()):
        if remaining <= 500:
            break
        path = _safe_relative_file(root_path, relative)
        if path is None:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="replace")
        allowed = min(file_limit, remaining)
        raw[relative] = text[:allowed]
        excerpt = _numbered_excerpt(text, max_chars=allowed)
        excerpts[relative] = excerpt
        remaining -= len(excerpt)
    return raw, excerpts


def _bounded_json(payload: object, limit: int = 32_000) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... deterministic context truncated ..."


def _build_user_prompt(
    changed_files: list[str],
    excerpts: dict[str, str],
    deterministic_context: dict[str, Any],
) -> str:
    sections = [
        "Review objective: independently check whether the change is safe to merge.",
        "\nChanged files declared by Git:\n" + "\n".join(f"- {path}" for path in changed_files),
        "\nDeterministic Sergeant evidence:\n" + _bounded_json(deterministic_context),
        "\nChanged-file excerpts follow. Paths and line numbers are authoritative.",
    ]
    for path, excerpt in excerpts.items():
        sections.append(f"\n--- FILE: {path} ---\n{excerpt}")
    if not excerpts:
        sections.append("\nNo readable changed-file excerpts were supplied. Do not invent code findings.")
    return "\n".join(sections)


def _line_range(raw_text: str, start: int, end: int) -> str:
    lines = raw_text.splitlines()
    if not lines:
        return ""
    start = max(1, min(start, len(lines)))
    end = max(start, min(end, len(lines)))
    return "\n".join(lines[start - 1 : end])


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}|\d+", text)
        if token.lower() not in {"the", "and", "for", "with", "this", "that", "from", "into"}
    }


def _evidence_supported(evidence: str, line_text: str, whole_file: str) -> bool:
    evidence_clean = evidence.strip().strip("`\"'")
    if len(evidence_clean) < 3:
        return False
    if evidence_clean in line_text or evidence_clean in whole_file:
        return True
    evidence_tokens = _tokens(evidence_clean)
    if not evidence_tokens:
        return False
    target_tokens = _tokens(line_text or whole_file)
    overlap = len(evidence_tokens & target_tokens) / max(1, len(evidence_tokens))
    return overlap >= 0.6


def _normalize_finding(raw: object, files: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    severity = str(raw.get("severity", "note")).strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        severity = "note"
    path = str(raw.get("path", "")).strip()
    if path not in files:
        return None
    try:
        line_start = int(raw.get("line_start", 1))
        line_end = int(raw.get("line_end", line_start))
    except (TypeError, ValueError):
        return None
    if line_start < 1 or line_end < line_start:
        return None
    line_count = max(1, len(files[path].splitlines()))
    if line_start > line_count:
        return None
    line_end = min(line_end, line_count)

    message = str(raw.get("message", "")).strip()
    evidence = str(raw.get("evidence", "")).strip()
    why = str(raw.get("why_it_matters", "")).strip()
    safer = str(raw.get("safer_alternative", "")).strip()
    if not message or not evidence or not why:
        return None

    line_text = _line_range(files[path], line_start, line_end)
    supported = _evidence_supported(evidence, line_text, files[path])
    if not supported:
        if severity in {"blocker", "major"}:
            return None
        severity = "note"

    candidate = {
        "severity": severity,
        "category": str(raw.get("category", "other")).strip().lower() or "other",
        "path": path,
        "line_start": line_start,
        "line_end": line_end,
        "message": message,
        "evidence": evidence,
        "evidence_verified": supported,
        "why_it_matters": why,
        "safer_alternative": safer,
    }
    root_cause = finding_root_cause(candidate)
    if root_cause:
        candidate["root_cause"] = root_cause
    return candidate


def _validate_pass(
    payload: dict[str, Any],
    files: dict[str, str],
    *,
    route: LLMRoute,
    assignment: CplAssignment | None = None,
) -> dict[str, Any]:
    raw_verdict = str(payload.get("verdict", "PASS")).strip().upper()
    if raw_verdict not in ALLOWED_VERDICTS:
        raw_verdict = "PASS"
    try:
        confidence = float(payload.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(1.0, max(0.0, confidence))
    findings = [
        finding
        for finding in (_normalize_finding(item, files) for item in payload.get("findings", []))
        if finding is not None
    ] if isinstance(payload.get("findings", []), list) else []

    if any(item["severity"] == "blocker" for item in findings):
        verdict = "BLOCK"
    elif any(item["severity"] == "major" for item in findings):
        verdict = "NEEDS WORK"
    else:
        verdict = "PASS"

    coverage = payload.get("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    files_reviewed = coverage.get("files_reviewed", [])
    if not isinstance(files_reviewed, list):
        files_reviewed = []
    files_reviewed = [str(path) for path in files_reviewed if str(path) in files]
    areas = coverage.get("areas", [])
    if not isinstance(areas, list):
        areas = []
    questions = payload.get("unanswered_questions", [])
    if not isinstance(questions, list):
        questions = []

    specialist = assignment.specialist if assignment is not None else "generalist"
    title = assignment.title if assignment is not None else "General Reasoning Specialist"
    return {
        "officer": "Cpl",
        "role": "Corporal Specialist",
        "specialist": specialist,
        "specialist_title": title,
        "model": route.model,
        "provider": route.provider,
        "protocol": route.protocol,
        "raw_verdict": raw_verdict,
        "verdict": verdict,
        "confidence": confidence,
        "summary": str(payload.get("summary", "")).strip(),
        "findings": findings,
        "unanswered_questions": [str(item) for item in questions if str(item).strip()],
        "coverage": {
            "files_reviewed": files_reviewed,
            "areas": [str(item) for item in areas if str(item).strip()],
        },
    }


def _merge_passes(passes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, float]:
    findings: list[dict[str, Any]] = []
    for item in passes:
        for finding in item.get("findings", []):
            merged = next((existing for existing in findings if findings_match(existing, finding)), None)
            if merged is None:
                findings.append({
                    **finding,
                    "supporting_models": [item.get("model")],
                    "supporting_specialists": [item.get("specialist")],
                })
                continue
            incoming_severity = str(finding.get("severity") or "note")
            existing_severity = str(merged.get("severity") or "note")
            if SEVERITY_RANK.get(incoming_severity, 0) > SEVERITY_RANK.get(existing_severity, 0):
                for field in (
                    "severity",
                    "category",
                    "path",
                    "line_start",
                    "line_end",
                    "message",
                    "evidence",
                    "evidence_verified",
                    "why_it_matters",
                    "safer_alternative",
                    "root_cause",
                ):
                    if field in finding:
                        merged[field] = finding[field]
            models = merged.setdefault("supporting_models", [])
            if item.get("model") not in models:
                models.append(item.get("model"))
            specialists = merged.setdefault("supporting_specialists", [])
            if item.get("specialist") not in specialists:
                specialists.append(item.get("specialist"))
    if any(item.get("severity") == "blocker" for item in findings):
        verdict = "BLOCK"
    elif any(item.get("severity") == "major" for item in findings):
        verdict = "NEEDS WORK"
    else:
        verdict = "PASS"
    confidence = sum(float(item.get("confidence", 0.5)) for item in passes) / max(1, len(passes))
    if len(passes) > 1 and len({item.get("verdict") for item in passes}) > 1:
        confidence = max(0.0, confidence - 0.15)
    return findings, verdict, round(confidence, 3)


def run_cpl_review(
    root: str | Path,
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    settings: LLMSettings | None = None,
    route: LLMRoute | None = None,
) -> dict[str, Any]:
    """Run Cpl's provider-routed adaptive specialist review."""

    settings = settings or LLMSettings.from_environment()
    identity = {"officer": "Cpl", "role": "Corporal Specialist"}
    if not settings.enabled:
        return {
            **identity,
            "enabled": False,
            "status": "disabled",
            "policy": settings.policy,
            "depth": cpl_depth(),
            "verdict": "PASS",
            "confidence": 0.0,
            "findings": [],
            "passes": [],
            "reasoning_plan": [],
            "reason": "Cpl reasoning is disabled by configuration.",
        }

    route = route or discover_route(settings)
    if route is None:
        return {
            **identity,
            "enabled": True,
            "status": "unavailable",
            "policy": settings.policy,
            "depth": cpl_depth(),
            "verdict": "NEEDS WORK" if settings.policy == "required" else "PASS",
            "confidence": 0.0,
            "findings": [],
            "passes": [],
            "reasoning_plan": [],
            "reason": "No configured Cpl, OpenAI-compatible, Ollama, or LM Studio model endpoint was available.",
            "settings": settings.public_dict(),
        }

    files, excerpts = collect_changed_file_excerpts(root, changed_files)
    user_prompt = _build_user_prompt(changed_files, excerpts, deterministic_context)
    passes: list[dict[str, Any]] = []
    errors: list[str] = []
    route_failovers: list[dict[str, Any]] = []

    try:
        primary_payload, primary_route, failed_models = _invoke_json_with_failover(
            route,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        if failed_models:
            route_failovers.append({
                "pass": "generalist",
                "failed_models": failed_models,
                "completed_by": primary_route.model,
            })
        primary = _validate_pass(primary_payload, files, route=primary_route)
        passes.append(primary)
    except LLMProviderError as error:
        errors.append(str(error))
        exhausted_models = list(error.failed_models)
        if exhausted_models:
            route_failovers.append({
                "pass": "generalist",
                "failed_models": exhausted_models,
                "completed_by": None,
            })
        return {
            **identity,
            "enabled": True,
            "status": "error",
            "policy": settings.policy,
            "depth": cpl_depth(),
            "route": route.public_dict(),
            "verdict": "NEEDS WORK" if settings.policy == "required" else "PASS",
            "confidence": 0.0,
            "findings": [],
            "passes": [],
            "reasoning_plan": [],
            "reason": "Cpl could not complete its primary reasoning pass.",
            "errors": errors,
            "route_failovers": route_failovers,
        }

    assignments = plan_cpl_assignments(
        changed_files,
        deterministic_context,
        primary_verdict=primary.get("verdict", "PASS"),
    )
    used_models = {str(primary.get("model") or route.model)}
    completed_plan: list[dict[str, object]] = []
    for assignment in assignments:
        specialist_route = route_for_assignment(route, assignment, used_models=used_models)
        plan_entry = {**assignment.to_dict(), "model": specialist_route.model}
        completed_plan.append(plan_entry)
        try:
            payload, completed_route, failed_models = _invoke_json_with_failover(
                specialist_route,
                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),
                user_prompt=user_prompt,
            )
            plan_entry["model"] = completed_route.model
            if failed_models:
                route_failovers.append({
                    "pass": assignment.specialist,
                    "failed_models": failed_models,
                    "completed_by": completed_route.model,
                })
            passes.append(_validate_pass(payload, files, route=completed_route, assignment=assignment))
            used_models.add(completed_route.model)
        except LLMProviderError as error:
            exhausted_models = list(error.failed_models)
            if exhausted_models:
                route_failovers.append({
                    "pass": assignment.specialist,
                    "failed_models": exhausted_models,
                    "completed_by": None,
                })
            errors.append(f"{assignment.specialist}: {error}")

    findings, verdict, confidence = _merge_passes(passes)
    reviewed_files = sorted({path for item in passes for path in item.get("coverage", {}).get("files_reviewed", [])})
    areas = sorted({area for item in passes for area in item.get("coverage", {}).get("areas", [])})
    questions = sorted({question for item in passes for question in item.get("unanswered_questions", [])})

    return {
        **identity,
        "enabled": True,
        "status": "completed" if not errors else "completed_with_warnings",
        "policy": settings.policy,
        "depth": cpl_depth(),
        "route": route.public_dict(),
        "verdict": verdict,
        "confidence": confidence,
        "summary": " ".join(item.get("summary", "") for item in passes if item.get("summary")).strip(),
        "findings": findings,
        "passes": passes,
        "reasoning_plan": completed_plan,
        "coverage": {
            "declared_changed_files": list(dict.fromkeys(changed_files)),
            "readable_files_supplied": sorted(files),
            "files_reviewed": reviewed_files,
            "areas": areas,
        },
        "unanswered_questions": questions,
        "errors": errors,
        "route_failovers": route_failovers,
        "reason": "Cpl specialist findings were validated against supplied repository text before entering Sergeant consensus.",
    }


def run_llm_review(
    root: str | Path,
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    settings: LLMSettings | None = None,
    route: LLMRoute | None = None,
) -> dict[str, Any]:
    """Compatibility alias for integrations using Sergeant 0.4.0 naming."""

    return run_cpl_review(
        root,
        changed_files,
        deterministic_context,
        settings=settings,
        route=route,
    )
