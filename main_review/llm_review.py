"""Evidence-grounded LLM review for Sergeant.

The semantic layer is additive: deterministic evidence remains authoritative and
an LLM may only contribute findings that can be tied back to supplied repository
text.  Unsupported or out-of-scope findings are rejected before consensus.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from .llm_provider import (
    LLMProviderError,
    LLMRoute,
    LLMSettings,
    PREFERRED_MODEL_NEEDLES,
    discover_route,
    invoke_json,
)

ALLOWED_VERDICTS = {"PASS", "NEEDS WORK", "BLOCK"}
ALLOWED_SEVERITIES = {"blocker", "major", "minor", "note"}
HIGH_RISK_PATH_PARTS = (
    ".github/",
    "scripts/",
    "deploy/",
    "auth",
    "security",
    "payment",
    "billing",
    "database",
    "migration",
    "permissions",
    "secrets",
)

SYSTEM_PROMPT = """You are Sergeant's independent semantic code reviewer.

Rules:
1. Review only the supplied changed-file excerpts and deterministic evidence.
2. Never invent files, lines, behavior, tests, or runtime results.
3. Every blocker or major finding must name a supplied path, a line range, and
   exact evidence grounded in that range.
4. Distinguish a demonstrated defect from a question or missing proof.
5. Treat deterministic tests and runtime evidence as stronger than speculation.
6. Stay read-only. Do not propose automatic merge or direct repository writes.
7. Return JSON only. Do not wrap it in Markdown.

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


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
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
    total_limit = max_total_chars or _int_env(
        "SERGEANT_LLM_MAX_INPUT_CHARS", 120_000, minimum=8_000, maximum=1_000_000
    )
    file_limit = max_file_chars or _int_env(
        "SERGEANT_LLM_MAX_FILE_CHARS", 18_000, minimum=2_000, maximum=200_000
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
        # Unsupported major/blocker claims are discarded rather than allowed to
        # influence the merge verdict. Unsupported minor claims become notes.
        if severity in {"blocker", "major"}:
            return None
        severity = "note"

    return {
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


def _validate_pass(
    payload: dict[str, Any],
    files: dict[str, str],
    *,
    route: LLMRoute,
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

    return {
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


def _high_risk(changed_files: list[str], deterministic_context: dict[str, Any], primary: dict[str, Any]) -> bool:
    if primary.get("verdict") != "PASS":
        return True
    if len(changed_files) >= 8:
        return True
    if any(part in path.lower() for path in changed_files for part in HIGH_RISK_PATH_PARTS):
        return True
    text = json.dumps(deterministic_context, default=str).lower()
    return '"verdict": "block"' in text or '"verdict": "needs work"' in text or '"passed": false' in text


def _select_challenger(route: LLMRoute) -> str:
    configured = os.getenv("SERGEANT_LLM_CHALLENGER_MODEL", "").strip()
    if configured and configured != route.model:
        return configured
    for needle in PREFERRED_MODEL_NEEDLES:
        for model in route.discovered_models:
            if model != route.model and needle in model.lower():
                return model
    return ""


def _finding_key(finding: dict[str, Any]) -> tuple[object, ...]:
    message = re.sub(r"\W+", " ", str(finding.get("message", "")).lower()).strip()
    return (
        finding.get("path"),
        finding.get("line_start"),
        finding.get("line_end"),
        message,
    )


def _merge_passes(passes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, float]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    for item in passes:
        for finding in item.get("findings", []):
            key = _finding_key(finding)
            if key not in merged:
                merged[key] = {**finding, "supporting_models": [item.get("model")]}
            else:
                models = merged[key].setdefault("supporting_models", [])
                if item.get("model") not in models:
                    models.append(item.get("model"))
    findings = list(merged.values())
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


def run_llm_review(
    root: str | Path,
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    settings: LLMSettings | None = None,
    route: LLMRoute | None = None,
) -> dict[str, Any]:
    """Run Sergeant's provider-routed semantic review council."""

    settings = settings or LLMSettings.from_environment()
    if not settings.enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "policy": settings.policy,
            "verdict": "PASS",
            "confidence": 0.0,
            "findings": [],
            "reason": "Semantic review is disabled by configuration.",
        }

    route = route or discover_route(settings)
    if route is None:
        return {
            "enabled": True,
            "status": "unavailable",
            "policy": settings.policy,
            "verdict": "NEEDS WORK" if settings.policy == "required" else "PASS",
            "confidence": 0.0,
            "findings": [],
            "reason": "No configured or local FCC/OpenAI-compatible/Ollama/LM Studio model endpoint was available.",
            "settings": settings.public_dict(),
        }

    files, excerpts = collect_changed_file_excerpts(root, changed_files)
    user_prompt = _build_user_prompt(changed_files, excerpts, deterministic_context)
    passes: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        primary_payload = invoke_json(route, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        primary = _validate_pass(primary_payload, files, route=route)
        passes.append(primary)
    except LLMProviderError as error:
        errors.append(str(error))
        return {
            "enabled": True,
            "status": "error",
            "policy": settings.policy,
            "route": route.public_dict(),
            "verdict": "NEEDS WORK" if settings.policy == "required" else "PASS",
            "confidence": 0.0,
            "findings": [],
            "reason": "The semantic reviewer could not complete its primary pass.",
            "errors": errors,
        }

    council_mode = os.getenv("SERGEANT_LLM_COUNCIL", "adaptive").strip().lower()
    challenger_model = _select_challenger(route)
    should_challenge = council_mode == "always" or (
        council_mode not in {"single", "off", "disabled"}
        and challenger_model
        and _high_risk(changed_files, deterministic_context, primary)
    )
    if should_challenge and challenger_model:
        challenger_route = replace(route, model=challenger_model)
        try:
            challenger_payload = invoke_json(
                challenger_route,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            passes.append(_validate_pass(challenger_payload, files, route=challenger_route))
        except LLMProviderError as error:
            errors.append(str(error))

    findings, verdict, confidence = _merge_passes(passes)
    reviewed_files = sorted({path for item in passes for path in item.get("coverage", {}).get("files_reviewed", [])})
    areas = sorted({area for item in passes for area in item.get("coverage", {}).get("areas", [])})
    questions = sorted({question for item in passes for question in item.get("unanswered_questions", [])})

    return {
        "enabled": True,
        "status": "completed" if not errors else "completed_with_warnings",
        "policy": settings.policy,
        "route": route.public_dict(),
        "verdict": verdict,
        "confidence": confidence,
        "summary": " ".join(item.get("summary", "") for item in passes if item.get("summary")).strip(),
        "findings": findings,
        "passes": passes,
        "coverage": {
            "declared_changed_files": list(dict.fromkeys(changed_files)),
            "readable_files_supplied": sorted(files),
            "files_reviewed": reviewed_files,
            "areas": areas,
        },
        "unanswered_questions": questions,
        "errors": errors,
        "reason": "Semantic findings were validated against supplied repository text before entering consensus.",
    }
