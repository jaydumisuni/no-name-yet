"""Council-led Cpl runtime with officer feedback and verified experience."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .cpl_council import (
    CATEGORY_SPECIALIST,
    agreement,
    assess,
    available_models,
    finding_key,
    finding_reference,
    findings_match,
    gap_signature,
    instruction,
    max_members,
    max_rounds,
    specialist_for_text,
)
from .cpl_council_prompt import follow_up_prompt, member_records, report_table
from .cpl_experience import detect_recurrences, retrieve_experience
from .cpl_reasoning import SPECIALISTS, specialist_system_prompt
from .cpl_reliability import attach_model_profiles, model_score, rank_models
from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route, invoke_json
from .llm_review import (
    SYSTEM_PROMPT,
    _build_user_prompt,
    _merge_passes,
    _validate_pass,
    collect_changed_file_excerpts,
    run_cpl_review as run_cpl_review_once,
)

ALLOWED_RESOLUTION_DISPOSITIONS = {"confirmed", "rejected", "narrowed", "not_applicable", "unresolved"}


def _annotate_base(result: dict[str, Any]) -> None:
    plan = {str(item.get("specialist")): item for item in result.get("reasoning_plan", []) if isinstance(item, dict)}
    for report in result.get("passes", []):
        specialist = str(report.get("specialist") or "generalist")
        report.setdefault("council_round", 1)
        report.setdefault("council_member_role", "core_member")
        report.setdefault("supported_officer", plan.get(specialist, {}).get("officer") or ("Cpl" if specialist == "generalist" else None))


def _bounded_route(route: LLMRoute, member_limit: int) -> LLMRoute:
    models = available_models(route)[:member_limit]
    if route.model not in models:
        models.insert(0, route.model)
    return replace(route, discovered_models=tuple(models[:member_limit]))


def _reliability_route(route: LLMRoute, settings: LLMSettings, experience: dict[str, Any]) -> LLMRoute:
    ranked = rank_models(available_models(route), experience)
    primary = route.model
    if not str(settings.model or "").strip() and ranked:
        primary = ranked[0]
    return replace(route, model=primary, discovered_models=tuple(ranked))


def _choose_model(models: list[str], used: set[str], fallback: str, member_limit: int) -> tuple[str, str]:
    unused = [model for model in models if model not in used]
    if unused and len(used) < member_limit:
        return unused[0], "new_member"
    return fallback, "role_separated_reuse"


def _coverage(passes: list[dict[str, Any]], original: dict[str, Any]) -> dict[str, Any]:
    files = sorted({path for item in passes for path in item.get("coverage", {}).get("files_reviewed", [])})
    areas = sorted({area for item in passes for area in item.get("coverage", {}).get("areas", [])})
    return {**original, "files_reviewed": files, "areas": areas}


def _resolved(passes: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        tuple(str(part) for part in item.get("resolved_gap_signature", []))
        for item in passes
        if item.get("resolution_status") == "answered" and len(item.get("resolved_gap_signature", [])) == 3
    }


def _normalize_resolution(payload: dict[str, Any], command: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("council_resolution")
    raw = raw if isinstance(raw, dict) else {}
    status = str(raw.get("status") or "unresolved").strip().lower()
    disposition = str(raw.get("disposition") or "unresolved").strip().lower()
    if disposition not in ALLOWED_RESOLUTION_DISPOSITIONS:
        disposition = "unresolved"
    answer = str(raw.get("answer") or "").strip()
    target = command.get("target_finding")

    answered = status == "answered" and disposition != "unresolved" and bool(answer) and not report.get("unanswered_questions")
    if target and disposition not in {"confirmed", "rejected", "narrowed"}:
        answered = False
    if not target and disposition not in {"confirmed", "rejected", "narrowed", "not_applicable"}:
        answered = False

    return {
        "status": "answered" if answered else "unresolved",
        "disposition": disposition if answered else "unresolved",
        "answer": answer,
        "target_finding": target,
        "gap_signature": command.get("gap_signature", []),
    }


def _effective_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered":
            continue
        if resolution.get("disposition") not in {"rejected", "narrowed"}:
            continue
        target = resolution.get("target_finding")
        if isinstance(target, dict):
            rejected.append(target)

    effective: list[dict[str, Any]] = []
    for report in passes:
        clone = dict(report)
        clone["findings"] = [
            finding
            for finding in report.get("findings", [])
            if not any(findings_match(finding, target) for target in rejected)
        ]
        effective.append(clone)
    return effective


def _annotate_confirmations(findings: list[dict[str, Any]], passes: list[dict[str, Any]]) -> None:
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered" or resolution.get("disposition") != "confirmed":
            continue
        target = resolution.get("target_finding")
        if not isinstance(target, dict):
            continue
        finding = next((item for item in findings if findings_match(item, target)), None)
        if finding is None:
            continue
        confirmations = finding.setdefault("council_confirmed_by", [])
        model = report.get("model")
        if model and model not in confirmations:
            confirmations.append(model)


def _recurrence_gaps(passes: list[dict[str, Any]], experience: dict[str, Any]) -> list[dict[str, Any]]:
    findings, _, _ = _merge_passes(passes)
    resolved = _resolved(passes)
    gaps: list[dict[str, Any]] = []
    for recurrence in detect_recurrences(findings, experience):
        matching = next((item for item in findings if item.get("message") == recurrence.get("current_finding")), {})
        specialist = specialist_for_text(recurrence.get("current_finding"))
        if specialist == "correctness":
            specialist = CATEGORY_SPECIALIST.get(str(matching.get("category") or "other"), "correctness")
        gap = {
            "type": "recurrence",
            "specialist": specialist,
            "officer": SPECIALISTS[specialist].officer,
            "reason": (
                f"Possible recurrence of {recurrence.get('previous_event_id')}: "
                f"{recurrence.get('current_finding')}. Determine why prior prevention did not stop it."
            ),
            "recurrence": recurrence,
            "target_finding": finding_reference(matching) if matching else None,
        }
        if gap_signature(gap) not in resolved:
            gaps.append(gap)
    return gaps


def _all_gaps(passes: list[dict[str, Any]], plan: list[dict[str, Any]], errors: list[str], models: list[str], experience: dict[str, Any]) -> list[dict[str, Any]]:
    effective = _effective_passes(passes)
    return [*_recurrence_gaps(effective, experience), *assess(effective, plan, errors, len(models))]


def _final_summary(round_count: int, member_count: int, findings: list[dict[str, Any]], final_gaps: list[dict[str, Any]]) -> str:
    return (
        f"Cpl completed {round_count} council round(s) with {member_count} distinct model member(s). "
        f"{len(findings)} effective grounded finding(s) remain and {len(final_gaps)} council gap(s) are unresolved."
    )


def run_cpl_review(
    root: str | Path,
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    settings: LLMSettings | None = None,
    route: LLMRoute | None = None,
) -> dict[str, Any]:
    """Run Cpl as an elastic model council commanding permanent officers."""

    root_path = Path(root)
    settings = settings or LLMSettings.from_environment()
    experience = retrieve_experience(root_path, changed_files, officers={item.officer for item in SPECIALISTS.values()})
    enriched_context = {
        **deterministic_context,
        "cpl_verified_experience": {
            "events": experience.get("events", [])[:12],
            "canonical_lessons": experience.get("canonical_lessons", [])[:8],
            "profiles": experience.get("profiles", {}),
            "anti_repeat_rule": experience.get("anti_repeat_rule"),
        },
    }
    discovered_route = route or (discover_route(settings) if settings.enabled else None)
    member_limit = max_members()
    reliability_route = _reliability_route(discovered_route, settings, experience) if discovered_route is not None else None
    resolved_route = _bounded_route(reliability_route, member_limit) if reliability_route is not None else None
    result = run_cpl_review_once(root_path, changed_files, enriched_context, settings=settings, route=resolved_route)
    result["experience"] = experience
    result["memory_checked"] = True

    if result.get("status") not in {"completed", "completed_with_warnings"} or resolved_route is None:
        result["council"] = {"mode": "not_deployed", "rounds": [], "members": [], "complete": result.get("status") == "disabled"}
        result["recurrences"] = []
        return result

    _annotate_base(result)
    passes = list(result.get("passes", []))
    plan = list(result.get("reasoning_plan", []))
    errors = list(result.get("errors", []))
    models = available_models(resolved_route)
    used = {str(item.get("model")) for item in passes if item.get("model")}
    rounds: list[dict[str, Any]] = []
    recruitment: list[dict[str, Any]] = []
    files, excerpts = collect_changed_file_excerpts(root_path, changed_files)
    base_prompt = _build_user_prompt(changed_files, excerpts, enriched_context)

    for round_number in range(2, max_rounds() + 1):
        gaps_before = _all_gaps(passes, plan, errors, models, experience)
        if not gaps_before:
            break
        gap = gaps_before[0]
        specialist = str(gap.get("specialist") or "correctness")
        assignment = SPECIALISTS.get(specialist, SPECIALISTS["correctness"])
        command = instruction(gap, round_number)
        ranked_candidates = rank_models(models, experience, specialist)
        selected_model, admission = _choose_model(ranked_candidates, used, resolved_route.model, member_limit)
        selected_route = replace(resolved_route, model=selected_model)
        recruited = {
            "round": round_number,
            "model": selected_model,
            "admission": admission,
            "required_capability": specialist,
            "reason": gap.get("reason"),
            "selection_score": model_score(selected_model, experience, specialist),
            "temporary": True,
        }
        recruitment.append(recruited)
        table = report_table(passes)
        officer_report: dict[str, Any] | None = None
        try:
            payload = invoke_json(
                selected_route,
                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),
                user_prompt=follow_up_prompt(base_prompt, table, command, experience, round_number),
            )
            officer_report = _validate_pass(payload, files, route=selected_route, assignment=assignment)
            resolution = _normalize_resolution(payload, command, officer_report)
            officer_report.update({
                "council_round": round_number,
                "council_member_role": "recruited_gap_specialist",
                "supported_officer": assignment.officer,
                "instruction_received": command,
                "admission": admission,
                "selection_score": recruited["selection_score"],
                "council_resolution": resolution,
                "resolved_gap_signature": resolution.get("gap_signature", []),
                "resolution_status": resolution.get("status"),
            })
            passes.append(officer_report)
            used.add(selected_model)
        except LLMProviderError as error:
            errors.append(f"council round {round_number} / {specialist}: {error}")
        rounds.append({
            "round": round_number,
            "table": table,
            "gaps_before": gaps_before,
            "instructions": [command],
            "recruitment": recruited,
            "officer_report": officer_report,
            "gaps_after": _all_gaps(passes, plan, errors, models, experience),
        })

    effective_passes = _effective_passes(passes)
    findings, verdict, confidence = _merge_passes(effective_passes)
    _annotate_confirmations(findings, passes)
    final_gaps = _all_gaps(passes, plan, errors, models, experience)
    if final_gaps and verdict == "PASS":
        verdict = "NEEDS WORK"
    unique_models = {str(item.get("model")) for item in passes if item.get("model")}
    independence = round(len(unique_models) / max(1, len(passes)), 3)
    if final_gaps:
        confidence = max(0.0, confidence - min(0.25, 0.04 * len(final_gaps)))
    if len(passes) > 1 and len(unique_models) == 1:
        confidence = max(0.0, confidence - 0.12)

    unresolved_questions = sorted({
        str(gap.get("reason"))
        for gap in final_gaps
        if gap.get("type") == "unanswered_question" and str(gap.get("reason", "")).strip()
    })
    round_count = 1 + len(rounds)
    result.update({
        "status": "completed" if not errors else "completed_with_warnings",
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "summary": _final_summary(round_count, len(unique_models), findings, final_gaps),
        "findings": findings,
        "passes": passes,
        "coverage": _coverage(effective_passes, result.get("coverage", {})),
        "unanswered_questions": unresolved_questions,
        "errors": errors,
        "reason": "Cpl retrieved verified experience, selected council members from proven service records, tabled officer reports, explicitly adjudicated earlier findings, and returned grounded evidence to Sergeant.",
    })
    result["recurrences"] = detect_recurrences(findings, experience)
    result["council"] = {
        "mode": "elastic_multi_model" if len(unique_models) > 1 else "single_model_role_separated",
        "core_round": 1,
        "rounds": rounds,
        "round_count": round_count,
        "max_rounds": max_rounds(),
        "members": attach_model_profiles(member_records(passes), experience),
        "member_count": len(unique_models),
        "max_members": member_limit,
        "recruitment": recruitment,
        "agreement": agreement(passes),
        "model_independence": independence,
        "true_model_independence": len(unique_models) > 1,
        "final_gaps": final_gaps,
        "complete": not final_gaps,
        "limitations": ["Only one model served multiple role-separated passes."] if len(unique_models) == 1 and len(passes) > 1 else [],
        "officer_instructions": [command for item in rounds for command in item.get("instructions", [])],
        "effective_findings": findings,
    }
    return result


def run_llm_review(
    root: str | Path,
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    settings: LLMSettings | None = None,
    route: LLMRoute | None = None,
) -> dict[str, Any]:
    return run_cpl_review(root, changed_files, deterministic_context, settings=settings, route=route)
