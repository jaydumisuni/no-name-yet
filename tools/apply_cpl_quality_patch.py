from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one patch marker in {relative}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# llm_review.py: bounded model failover and normalized root-cause metadata.
replace_once(
    "main_review/llm_review.py",
    "import json\nimport os\nimport re\nfrom pathlib import Path\n",
    "import json\nimport os\nimport re\nfrom dataclasses import replace\nfrom pathlib import Path\n",
)
replace_once(
    "main_review/llm_review.py",
    "from .cpl_council import findings_match\n",
    "from .cpl_council import available_models, finding_root_cause, findings_match\n",
)
replace_once(
    "main_review/llm_review.py",
    "\n\ndef _env(primary: str, legacy: str, default: str) -> str:\n",
    '''\n\ndef _invoke_json_with_failover(\n    route: LLMRoute,\n    *,\n    system_prompt: str,\n    user_prompt: str,\n) -> tuple[dict[str, Any], LLMRoute, list[str]]:\n    """Try each configured council model before declaring the officer pass failed."""\n\n    failed_models: list[str] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError:\n            failed_models.append(model)\n    raise LLMProviderError(\n        "No configured Cpl council model completed the required structured officer pass."\n    )\n\n\ndef _env(primary: str, legacy: str, default: str) -> str:\n''',
)
replace_once(
    "main_review/llm_review.py",
    '''    return {\n        "severity": severity,\n        "category": str(raw.get("category", "other")).strip().lower() or "other",\n        "path": path,\n        "line_start": line_start,\n        "line_end": line_end,\n        "message": message,\n        "evidence": evidence,\n        "evidence_verified": supported,\n        "why_it_matters": why,\n        "safer_alternative": safer,\n    }\n''',
    '''    candidate = {\n        "severity": severity,\n        "category": str(raw.get("category", "other")).strip().lower() or "other",\n        "path": path,\n        "line_start": line_start,\n        "line_end": line_end,\n        "message": message,\n        "evidence": evidence,\n        "evidence_verified": supported,\n        "why_it_matters": why,\n        "safer_alternative": safer,\n    }\n    root_cause = finding_root_cause(candidate)\n    if root_cause:\n        candidate["root_cause"] = root_cause\n    return candidate\n''',
)
replace_once(
    "main_review/llm_review.py",
    '''    passes: list[dict[str, Any]] = []\n    errors: list[str] = []\n\n    try:\n        primary_payload = invoke_json(route, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)\n        primary = _validate_pass(primary_payload, files, route=route)\n        passes.append(primary)\n''',
    '''    passes: list[dict[str, Any]] = []\n    errors: list[str] = []\n    route_failovers: list[dict[str, Any]] = []\n\n    try:\n        primary_payload, primary_route, failed_models = _invoke_json_with_failover(\n            route,\n            system_prompt=SYSTEM_PROMPT,\n            user_prompt=user_prompt,\n        )\n        if failed_models:\n            route_failovers.append({\n                "pass": "generalist",\n                "failed_models": failed_models,\n                "completed_by": primary_route.model,\n            })\n        primary = _validate_pass(primary_payload, files, route=primary_route)\n        passes.append(primary)\n''',
)
replace_once(
    "main_review/llm_review.py",
    "    used_models = {route.model}\n",
    "    used_models = {str(primary.get(\"model\") or route.model)}\n",
)
replace_once(
    "main_review/llm_review.py",
    '''        try:\n            payload = invoke_json(\n                specialist_route,\n                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),\n                user_prompt=user_prompt,\n            )\n            passes.append(_validate_pass(payload, files, route=specialist_route, assignment=assignment))\n            used_models.add(specialist_route.model)\n''',
    '''        try:\n            payload, completed_route, failed_models = _invoke_json_with_failover(\n                specialist_route,\n                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),\n                user_prompt=user_prompt,\n            )\n            if failed_models:\n                route_failovers.append({\n                    "pass": assignment.specialist,\n                    "failed_models": failed_models,\n                    "completed_by": completed_route.model,\n                })\n            passes.append(_validate_pass(payload, files, route=completed_route, assignment=assignment))\n            used_models.add(completed_route.model)\n''',
)
replace_once(
    "main_review/llm_review.py",
    '''        "errors": errors,\n        "reason": "Cpl specialist findings were validated against supplied repository text before entering Sergeant consensus.",\n''',
    '''        "errors": errors,\n        "route_failovers": route_failovers,\n        "reason": "Cpl specialist findings were validated against supplied repository text before entering Sergeant consensus.",\n''',
)

# cpl_runtime.py: successful reassignments resolve route failures and rejected findings lose stale verdicts.
replace_once(
    "main_review/cpl_runtime.py",
    '''    _build_user_prompt,\n    _merge_passes,\n    _validate_pass,\n''',
    '''    _build_user_prompt,\n    _invoke_json_with_failover,\n    _merge_passes,\n    _validate_pass,\n''',
)
replace_once(
    "main_review/cpl_runtime.py",
    "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route, invoke_json\n",
    "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route\n",
)
replace_once(
    "main_review/cpl_runtime.py",
    "\n\ndef _effective_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:\n",
    '''\n\ndef _verdict_for_findings(findings: list[dict[str, Any]]) -> str:\n    if any(item.get("severity") == "blocker" for item in findings):\n        return "BLOCK"\n    if any(item.get("severity") == "major" for item in findings):\n        return "NEEDS WORK"\n    return "PASS"\n\n\ndef _effective_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:\n''',
)
replace_once(
    "main_review/cpl_runtime.py",
    '''        clone = dict(report)\n        clone["findings"] = [\n            finding\n            for finding in report.get("findings", [])\n            if not any(findings_match(finding, target) for target in rejected)\n        ]\n        effective.append(clone)\n''',
    '''        clone = dict(report)\n        clone["findings"] = [\n            finding\n            for finding in report.get("findings", [])\n            if not any(findings_match(finding, target) for target in rejected)\n        ]\n        clone["verdict"] = _verdict_for_findings(clone["findings"])\n        effective.append(clone)\n''',
)
replace_once(
    "main_review/cpl_runtime.py",
    '''            payload = invoke_json(\n                selected_route,\n                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),\n                user_prompt=follow_up_prompt(base_prompt, table, command, experience, round_number),\n            )\n            officer_report = _validate_pass(payload, files, route=selected_route, assignment=assignment)\n''',
    '''            payload, completed_route, failed_models = _invoke_json_with_failover(\n                selected_route,\n                system_prompt=specialist_system_prompt(SYSTEM_PROMPT, assignment),\n                user_prompt=follow_up_prompt(base_prompt, table, command, experience, round_number),\n            )\n            selected_model = completed_route.model\n            recruited["model"] = selected_model\n            if failed_models:\n                recruited["failover_from"] = failed_models\n            officer_report = _validate_pass(payload, files, route=completed_route, assignment=assignment)\n''',
)

# pr_reviewer.py: deterministic confirmations strengthen evidence without becoming duplicate actions.
replace_once(
    "main_review/pr_reviewer.py",
    "from .cpl_runtime import run_cpl_review\n",
    "from .cpl_noise import reconcile_cpl_findings\nfrom .cpl_runtime import run_cpl_review\n",
)
replace_once(
    "main_review/pr_reviewer.py",
    '''    if cpl.get("verdict") in {"BLOCK", "NEEDS WORK"}:\n        for finding in cpl.get("findings", []):\n''',
    '''    if cpl.get("decision_verdict", cpl.get("verdict")) in {"BLOCK", "NEEDS WORK"}:\n        for finding in cpl.get("actionable_findings", cpl.get("findings", [])):\n''',
)
replace_once(
    "main_review/pr_reviewer.py",
    "    cpl_verdict = cpl.get(\"verdict\")\n",
    "    cpl_verdict = cpl.get(\"decision_verdict\", cpl.get(\"verdict\"))\n",
)
replace_once(
    "main_review/pr_reviewer.py",
    '''        return {\n            "source": "cpl-reasoning",\n            "verdict": cpl.get("verdict"),\n            "evidence": cpl.get("findings", []),\n        }\n''',
    '''        return {\n            "source": "cpl-reasoning",\n            "verdict": cpl.get("decision_verdict", cpl.get("verdict")),\n            "evidence": cpl.get("decision_findings", cpl.get("findings", [])),\n        }\n''',
)
replace_once(
    "main_review/pr_reviewer.py",
    '''    cpl = run_cpl_review(root_path, semantic_files, cpl_context)\n\n    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}\n''',
    '''    cpl = run_cpl_review(root_path, semantic_files, cpl_context)\n    deterministic_findings = [\n        *repository_review.get("evidence", {}).get("findings", []),\n        *diff.get("evidence", {}).get("findings", []),\n        *capabilities.get("findings", []),\n        *intelligence.get("promoted_findings", []),\n    ]\n    cpl = reconcile_cpl_findings(cpl, deterministic_findings)\n\n    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}\n''',
)
replace_once(
    "main_review/pr_reviewer.py",
    '''    lines.append(f"- Cpl verdict: {cpl.get('verdict')}")\n    lines.append(f"- Cpl confidence: {cpl.get('confidence')}")\n''',
    '''    lines.append(f"- Cpl raw verdict: {cpl.get('verdict')}")\n    lines.append(f"- Cpl decision verdict: {cpl.get('decision_verdict', cpl.get('verdict'))}")\n    lines.append(f"- Cpl confidence: {cpl.get('confidence')}")\n''',
)
replace_once(
    "main_review/pr_reviewer.py",
    '''    cpl_findings = cpl.get("findings", []) if isinstance(cpl, dict) else []\n''',
    '''    cpl_findings = cpl.get("actionable_findings", cpl.get("findings", [])) if isinstance(cpl, dict) else []\n''',
)

# review_benchmark.py: measure the governed actionable surface, not audit confirmations/advisories.
replace_once(
    "main_review/review_benchmark.py",
    '''    cpl = packet.get("cpl_review", packet.get("semantic_review", {}))\n    if isinstance(cpl, dict):\n        raw.extend(("cpl", item) for item in cpl.get("findings", []) if isinstance(item, dict))\n''',
    '''    cpl = packet.get("cpl_review", packet.get("semantic_review", {}))\n    if isinstance(cpl, dict):\n        cpl_findings = cpl.get("actionable_findings")\n        if not isinstance(cpl_findings, list):\n            cpl_findings = cpl.get("findings", [])\n        raw.extend(("cpl", item) for item in cpl_findings if isinstance(item, dict))\n''',
)

# Idempotency and construction checks.
for relative, markers in {
    "main_review/llm_review.py": ["def _invoke_json_with_failover("],
    "main_review/cpl_runtime.py": ["def _verdict_for_findings("],
    "main_review/pr_reviewer.py": ["reconcile_cpl_findings(cpl, deterministic_findings)"],
}.items():
    text = (ROOT / relative).read_text(encoding="utf-8")
    for marker in markers:
        if text.count(marker) != 1:
            raise SystemExit(f"Expected exactly one {marker!r} in {relative}")

print("Cpl quality patch applied successfully.")
