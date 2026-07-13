"""Cpl reasoning doctrine and officer-support mission planning.

Cpl is Sergeant's native Corporal Specialist. It is not a model name or a thin
provider proxy. Cpl decomposes a review mission, assigns evidence-focused model
bots to permanent officers, chooses available engines, and returns validated
evidence to Sergeant's deterministic consensus layer.

Permanent officers keep their doctrine and authority. Cpl amplifies them with
shared field intelligence and mission-specific reasoning support; it does not
replace them.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from .llm_provider import LLMRoute, PREFERRED_MODEL_NEEDLES

CplDepth = Literal["adaptive", "deep", "maximum", "single"]


@dataclass(frozen=True)
class CplAssignment:
    specialist: str
    officer: str
    officer_role: str
    title: str
    mission: str
    focus: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SPECIALISTS: dict[str, CplAssignment] = {
    "correctness": CplAssignment(
        "correctness",
        "Engineer",
        "Technical Construction",
        "Correctness Support Bot",
        "Help Engineer trace control flow, boundary conditions, state transitions, error handling, and behavior changes.",
        ("logic", "boundaries", "state", "errors", "regressions"),
    ),
    "security": CplAssignment(
        "security",
        "Medic",
        "Security, Diagnosis, and Safe Remediation",
        "Security Support Bot",
        "Help Medic trace trust boundaries, authentication, authorization, secrets, injection paths, unsafe execution, and repair risk.",
        ("trust boundaries", "auth", "permissions", "secrets", "injection"),
    ),
    "architecture": CplAssignment(
        "architecture",
        "Engineer",
        "Technical Construction",
        "Architecture Support Bot",
        "Help Engineer review contracts between modules, coupling, lifecycle, deployment effects, data ownership, and blast radius.",
        ("contracts", "coupling", "lifecycle", "deployment", "data flow"),
    ),
    "tests_contracts": CplAssignment(
        "tests_contracts",
        "Engineer",
        "Technical Construction",
        "Tests and Contracts Support Bot",
        "Help Engineer check whether tests, API contracts, workflow proof, documentation, and failure cases cover the changed behavior.",
        ("tests", "API contracts", "workflow proof", "docs", "failure cases"),
    ),
    "performance_concurrency": CplAssignment(
        "performance_concurrency",
        "Mechanic",
        "Runtime Behavior",
        "Performance and Concurrency Support Bot",
        "Help Mechanic inspect resource lifetime, asynchronous behavior, locking, retries, caching, scaling, and expensive paths.",
        ("async", "locking", "retries", "caching", "resource lifetime"),
    ),
}

SECURITY_TERMS = (
    "auth", "authentication", "authorization", "permission", "secret", "token",
    "password", "payment", "billing", "webhook", "crypto", "exec", "shell",
    "subprocess", "injection", "cors", "security", "src/auth", "src/security",
)
ARCHITECTURE_TERMS = (
    "deploy", "deployment", "workflow", ".github/workflows/", "database", "migration",
    "schema", "adapter", "provider", "router", "bridge", "service", "controller",
    "package.json", "pyproject.toml", "build.gradle", "dockerfile",
)
TEST_CONTRACT_TERMS = (
    "test", "tests/", "spec", "api_contract", "contract", ".github/workflows/",
    "readme", "docs/", "manifest", "package.json", "pyproject.toml", "gradle",
    "release", "proof",
)
PERFORMANCE_TERMS = (
    "async", "await", "thread", "lock", "queue", "cache", "retry", "timeout",
    "stream", "batch", "parallel", "performance", "memory", "latency",
)
CORRECTNESS_TERMS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".cs", ".php", ".rb", ".swift",
)

# Only evidence-bearing fields are allowed to influence adaptive deployment.
# Generic metadata such as a capability named "security_taint" being available
# must not silently deploy the Medic security support bot on every mission.
EVIDENCE_KEYS = {
    "findings",
    "ranked_findings",
    "repository_findings",
    "diff_findings",
    "blockers",
    "required_actions",
    "unanswered_questions",
    "errors",
}


def _env(primary: str, legacy: str, default: str) -> str:
    value = os.getenv(primary)
    if value is not None:
        return value
    return os.getenv(legacy, default)


def cpl_depth() -> CplDepth:
    explicit = os.getenv("SERGEANT_CPL_DEPTH")
    if explicit is None:
        explicit = os.getenv("SERGEANT_LLM_DEPTH")
    if explicit is None:
        explicit = os.getenv("SERGEANT_CPL_COUNCIL")
    if explicit is None:
        explicit = os.getenv("SERGEANT_LLM_COUNCIL", "adaptive")
    value = explicit.strip().lower()
    aliases = {
        "max": "maximum",
        "full": "maximum",
        "always": "maximum",
        "off": "single",
        "disabled": "single",
    }
    value = aliases.get(value, value)
    return value if value in {"adaptive", "deep", "maximum", "single"} else "adaptive"  # type: ignore[return-value]


def cpl_max_passes() -> int:
    default = {"single": 1, "adaptive": 3, "deep": 4, "maximum": 6}[cpl_depth()]
    try:
        value = int(_env("SERGEANT_CPL_MAX_PASSES", "SERGEANT_LLM_MAX_PASSES", str(default)))
    except ValueError:
        value = default
    return min(8, max(1, value))


def _evidence_strings(value: object, *, inside_evidence: bool = False) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            strings.extend(_evidence_strings(item, inside_evidence=inside_evidence or key in EVIDENCE_KEYS))
    elif isinstance(value, list):
        for item in value:
            strings.extend(_evidence_strings(item, inside_evidence=inside_evidence))
    elif inside_evidence and value is not None:
        strings.append(str(value))
    return strings


def _context_text(changed_files: list[str], deterministic_context: dict[str, Any]) -> str:
    evidence = _evidence_strings(deterministic_context)
    return ("\n".join(changed_files) + "\n" + "\n".join(evidence)).lower()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        normalized = term.lower()
        if any(not char.isalnum() and char != "_" for char in normalized):
            if normalized in text:
                return True
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(normalized)}(?![a-z0-9_])", text):
            return True
    return False


def plan_cpl_assignments(
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    primary_verdict: str = "PASS",
) -> list[CplAssignment]:
    """Plan permanent-officer support bots after Cpl's general field pass.

    The plan is deterministic and auditable. Model output cannot choose which
    officer receives support or silently expand the files in scope.
    """

    depth = cpl_depth()
    if depth == "single":
        return []

    text = _context_text(changed_files, deterministic_context)
    selected: list[str] = []

    def add(name: str) -> None:
        if name not in selected:
            selected.append(name)

    # Priority is risk first, then system shape, contracts, correctness, and
    # expensive runtime behavior. The pass budget truncates this exact order.
    if _contains(text, SECURITY_TERMS):
        add("security")
    if len(changed_files) >= 4 or _contains(text, ARCHITECTURE_TERMS):
        add("architecture")
    if primary_verdict != "PASS" or _contains(text, TEST_CONTRACT_TERMS):
        add("tests_contracts")
    if primary_verdict != "PASS" or _contains(text, CORRECTNESS_TERMS):
        add("correctness")
    if _contains(text, PERFORMANCE_TERMS):
        add("performance_concurrency")

    if depth in {"deep", "maximum"}:
        add("correctness")
        add("architecture")
        add("tests_contracts")
    if depth == "maximum":
        add("security")
        add("performance_concurrency")

    limit = max(0, cpl_max_passes() - 1)
    return [SPECIALISTS[name] for name in selected[:limit]]


def _model_env_name(specialist: str) -> tuple[str, str]:
    token = re.sub(r"[^A-Z0-9]+", "_", specialist.upper()).strip("_")
    return f"SERGEANT_CPL_{token}_MODEL", f"SERGEANT_LLM_{token}_MODEL"


def model_for_assignment(
    route: LLMRoute,
    assignment: CplAssignment,
    *,
    used_models: set[str],
) -> str:
    """Choose an explicit officer-support model or rotate preferred models."""

    primary_env, legacy_env = _model_env_name(assignment.specialist)
    configured = _env(primary_env, legacy_env, "").strip()
    if configured:
        return configured

    ordered: list[str] = []
    lowered = [(model, model.lower()) for model in route.discovered_models]
    for needle in PREFERRED_MODEL_NEEDLES:
        ordered.extend(model for model, normalized in lowered if needle in normalized and model not in ordered)
    ordered.extend(model for model in route.discovered_models if model not in ordered)

    for model in ordered:
        if model not in used_models:
            return model
    return route.model


def route_for_assignment(
    route: LLMRoute,
    assignment: CplAssignment,
    *,
    used_models: set[str],
) -> LLMRoute:
    return replace(route, model=model_for_assignment(route, assignment, used_models=used_models))


def specialist_system_prompt(base_prompt: str, assignment: CplAssignment) -> str:
    focus = ", ".join(assignment.focus)
    return (
        f"{base_prompt}\n\n"
        "CPL SPECIALIST ASSIGNMENT — OFFICER SUPPORT\n"
        "Commanding officer: Cpl — Corporal Specialist\n"
        f"Supported permanent officer: {assignment.officer}\n"
        f"Officer doctrine: {assignment.officer_role}\n"
        f"Support unit: {assignment.title}\n"
        f"Mission: {assignment.mission}\n"
        f"Focus: {focus}.\n"
        "You are a replaceable model-powered support bot attached to the named permanent officer. "
        "Cpl owns orchestration; the permanent officer owns the specialty, evidence obligations, and officer report. "
        "Do not impersonate Cpl or replace the permanent officer. Do not repeat generic observations merely to fill the report. "
        "Return only findings this support assignment can prove from the supplied evidence."
    )
