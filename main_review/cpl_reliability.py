"""Reliability-aware council member selection for Cpl."""
from __future__ import annotations

from typing import Any, Iterable

SPECIALIST_CATEGORIES = {
    "correctness": {"correctness", "maintainability"},
    "security": {"security"},
    "architecture": {"architecture", "api_contract", "maintainability"},
    "tests_contracts": {"tests", "api_contract", "documentation"},
    "performance_concurrency": {"performance", "concurrency"},
}


def _profile(experience: dict[str, Any], model: str) -> dict[str, Any]:
    profiles = experience.get("profiles", {})
    return profiles.get(f"model:{model}", {}) if isinstance(profiles, dict) else {}


def model_score(model: str, experience: dict[str, Any], specialist: str | None = None) -> float:
    """Score a model conservatively from verified outcomes.

    A neutral prior prevents one successful mission from creating instant trust.
    Repeated verified outcomes move the score gradually; rejected outcomes pull it
    down, and domain evidence adds only a small scoped bonus.
    """

    profile = _profile(experience, model)
    if not profile:
        return 0.5
    verified = int(profile.get("verified_outcomes", 0) or 0)
    rejected = int(profile.get("rejected_outcomes", 0) or 0)
    missions = max(int(profile.get("missions_recorded", 0) or 0), verified + rejected)
    posterior_reliability = (verified + 2.0) / (verified + rejected + 4.0)
    categories = {str(item) for item in profile.get("categories", [])}
    required = SPECIALIST_CATEGORIES.get(str(specialist or ""), set())
    category_bonus = 0.08 if required and categories & required else 0.0
    evidence_bonus = min(0.06, missions * 0.01)
    return round(min(1.0, posterior_reliability * 0.78 + 0.11 + category_bonus + evidence_bonus), 4)


def rank_models(models: Iterable[str], experience: dict[str, Any], specialist: str | None = None) -> list[str]:
    """Rank models stably by scoped verified reliability."""

    ordered = list(dict.fromkeys(str(model) for model in models if str(model).strip()))
    positions = {model: index for index, model in enumerate(ordered)}
    return sorted(
        ordered,
        key=lambda model: (-model_score(model, experience, specialist), positions[model]),
    )


def attach_model_profiles(members: list[dict[str, Any]], experience: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose the verified service record used by Cpl for each deployed member."""

    output: list[dict[str, Any]] = []
    for member in members:
        model = str(member.get("model") or "")
        output.append({
            **member,
            "experience_profile": _profile(experience, model),
            "selection_score": model_score(model, experience),
        })
    return output
