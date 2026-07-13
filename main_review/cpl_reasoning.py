"""Cpl reasoning doctrine and specialist mission planning.

Cpl is Sergeant's native Corporal Specialist. It is not a model name or a thin
provider proxy. Cpl decomposes a review mission, assigns evidence-focused
specialist passes, chooses available models, and returns the validated evidence
to Sergeant's deterministic consensus layer.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from .llm_provider import LLMRoute, PREFERRED_MODEL_NEEDLES

CplDepth = Literal["adaptive", "deep", "maximum", "single"]


@dataclass(frozen=True)
class CplAssignment:
    specialist: str
    title: str
    mission: str
    focus: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SPECIALISTS: dict[str, CplAssignment] = {
    "correctness": CplAssignment(
        "correctness",
        "Correctness Specialist",
        "Trace control flow, boundary conditions, state transitions, error handling, and behavior changes.",
        ("logic", "boundaries", "state", "errors", "regressions"),
    ),
    "security": CplAssignment(
        "security",
        "Security Specialist",
        "Trace trust boundaries, authentication, authorization, secrets, injection paths, and unsafe execution.",
        ("trust boundaries", "auth", "permissions", "secrets", "injection"),
    ),
    "architecture": CplAssignment(
        "architecture",
        "Architecture Specialist",
        "Review contracts between modules, coupling, lifecycle, deployment effects, data ownership, and blast radius.",
        ("contracts", "coupling", "lifecycle", "deployment", "data flow"),
    ),
    "tests_contracts": CplAssignment(
        "tests_contracts",
        "Tests and Contracts Specialist",
        "Check whether tests, API contracts, workflow proof, documentation, and failure cases cover the changed behavior.",
        ("tests", "API contracts", "workflow proof", "docs", "failure cases"),
    ),
    "performance_concurrency": CplAssignment(
        "performance_concurrency",
        "Performance and Concurrency Specialist",
        "Inspect resource lifetime, asynchronous behavior, locking, retries, caching, scaling, and expensive paths.",
        ("async", "locking", "retries", "caching", "resource lifetime"),
    ),
}

SECURITY_TERMS = (
    "auth", "permission", "secret", "token", "password", "payment", "billing",
    "webhook", "crypto", "exec", "shell", "subprocess", "injection", "cors",
)
ARCHITECTURE_TERMS = (
    "deploy", "workflow", "database", "migration", "schema", "adapter", "provider",
    "router", "bridge", "service", "controller", "repository", "package.json", "pyproject",
)
TEST_CONTRACT_TERMS = (
    "test", "spec", "api", "contract", "workflow", "readme", "docs/", "manifest",
    "package.json", "pyproject", "gradle", "release",
)
PERFORMANCE_TERMS = (
    "async", "await", "thread", "lock", "queue", "cache", "retry", "timeout",
    "stream", "batch", "parallel", "performance", "memory", "latency",
)
CORRECTNESS_TERMS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".cs", ".php", ".rb", ".swift",
)


def _env(primary: str, legacy: str, default: str) -> str:
    value = os.getenv(primary)
    if value is not None:
        return value
    return os.getenv(legacy, default)


def cpl_depth() -> CplDepth:
    value = _env("SERGEANT_CPL_DEPTH", "SERGEANT_LLM_DEPTH", "adaptive").strip().lower()
    aliases = {"max": "maximum", "full": "maximum", "off": "single"}
    value = aliases.get(value, value)
    return value if value in {"adaptive", "deep", "maximum", "single"} else "adaptive"  # type: ignore[return-value]


def cpl_max_passes() -> int:
    default = {"single": 1, "adaptive": 3, "deep": 4, "maximum": 6}[cpl_depth()]
    try:
        value = int(_env("SERGEANT_CPL_MAX_PASSES", "SERGEANT_LLM_MAX_PASSES", str(default)))
    except ValueError:
        value = default
    return min(8, max(1, value))


def _context_text(changed_files: list[str], deterministic_context: dict[str, Any]) -> str:
    return ("\n".join(changed_files) + "\n" + json.dumps(deterministic_context, default=str)).lower()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def plan_cpl_assignments(
    changed_files: list[str],
    deterministic_context: dict[str, Any],
    *,
    primary_verdict: str = "PASS",
) -> list[CplAssignment]:
    """Plan additional specialist passes after Cpl's general review.

    The plan is deterministic and auditable. Model output cannot choose which
    specialist gets deployed or silently expand the files in scope.
    """

    depth = cpl_depth()
    if depth == "single":
        return []

    text = _context_text(changed_files, deterministic_context)
    selected: list[str] = []

    def add(name: str) -> None:
        if name not in selected:
            selected.append(name)

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

    # The primary generalist pass already consumes one slot.
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
    """Choose an explicit specialist model or rotate through preferred models."""

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
        "CPL SPECIALIST ASSIGNMENT\n"
        f"Officer: Cpl — Corporal Specialist\n"
        f"Specialty: {assignment.title}\n"
        f"Mission: {assignment.mission}\n"
        f"Focus: {focus}.\n"
        "Do not repeat generic observations merely to fill the report. Return only findings that this specialty can prove from the supplied evidence."
    )
