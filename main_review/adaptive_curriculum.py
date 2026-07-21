"""Adaptive, evidence-gated curriculum planning for Sergeant training.

The planner raises repository difficulty only after Sergeant proves that the
current tier is becoming routine. It keeps Rust as a high-value accelerator
without allowing one language or one language family to dominate the training
stream. Work is budgeted using Sergeant's existing ten-times private-force law.

This module plans training only. It cannot promote lessons, alter verdicts, or
merge code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .operational_contracts import private_force_size

CURRICULUM_SCHEMA_VERSION = "sergeant.adaptive-curriculum.v1"
MIN_PROMOTION_SAMPLES = 3
PROMOTION_RECALL = 0.80
MAX_FALSE_POSITIVE_RATE = 0.10
RUST_WINDOW = 10
MAX_RUST_PER_WINDOW = 2


@dataclass(frozen=True)
class DifficultyTier:
    name: str
    max_changed_files: int | None
    max_changed_lines: int | None
    max_package_count: int | None
    max_dependency_depth: int | None


DIFFICULTY_TIERS: tuple[DifficultyTier, ...] = (
    DifficultyTier("focused", 4, 500, 1, 2),
    DifficultyTier("component", 12, 2_500, 2, 4),
    DifficultyTier("subsystem", 30, 8_000, 4, 6),
    DifficultyTier("system", 100, 25_000, 10, 10),
    DifficultyTier("large-system", None, None, None, None),
)

_LANGUAGE_ALIASES = {
    "c++": "cpp",
    "cxx": "cpp",
    "objective-c": "objective_c",
    "objective c": "objective_c",
    "c#": "csharp",
    "f#": "fsharp",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
}

_LANGUAGE_FAMILIES = {
    "rust": "systems",
    "c": "systems",
    "cpp": "systems",
    "zig": "systems",
    "go": "systems",
    "swift": "native-mobile",
    "objective_c": "native-mobile",
    "kotlin": "managed",
    "java": "managed",
    "scala": "managed",
    "csharp": "managed",
    "javascript": "web-runtime",
    "typescript": "web-runtime",
    "dart": "web-runtime",
    "python": "dynamic",
    "ruby": "dynamic",
    "perl": "dynamic",
    "php": "dynamic",
    "lua": "dynamic",
    "elixir": "functional-runtime",
    "erlang": "functional-runtime",
    "ocaml": "functional",
    "fsharp": "functional",
    "haskell": "functional",
    "clojure": "functional",
    "julia": "scientific",
    "r": "scientific",
    "nim": "compiled-multiparadigm",
    "crystal": "compiled-multiparadigm",
}


def normalize_language(value: object) -> str:
    language = str(value or "unknown").strip().lower().replace("-", "_")
    return _LANGUAGE_ALIASES.get(language, language)


def language_family(language: object) -> str:
    normalized = normalize_language(language)
    return _LANGUAGE_FAMILIES.get(normalized, f"other:{normalized}")


def _within(value: int, maximum: int | None) -> bool:
    return maximum is None or value <= maximum


def repository_difficulty(candidate: Mapping[str, Any]) -> int:
    """Return a stable difficulty tier from repository and change complexity."""

    changed_files = max(1, int(candidate.get("changed_files", 1) or 1))
    changed_lines = max(1, int(candidate.get("changed_lines", 1) or 1))
    package_count = max(1, int(candidate.get("package_count", 1) or 1))
    dependency_depth = max(0, int(candidate.get("dependency_depth", 0) or 0))

    tier = len(DIFFICULTY_TIERS) - 1
    for index, limits in enumerate(DIFFICULTY_TIERS):
        if (
            _within(changed_files, limits.max_changed_files)
            and _within(changed_lines, limits.max_changed_lines)
            and _within(package_count, limits.max_package_count)
            and _within(dependency_depth, limits.max_dependency_depth)
        ):
            tier = index
            break

    semantic_boost = 0
    if bool(candidate.get("cross_component")):
        semantic_boost += 1
    if bool(candidate.get("concurrency_or_lifecycle")):
        semantic_boost += 1
    if float(candidate.get("defect_novelty", 0.0) or 0.0) >= 0.75:
        semantic_boost += 1
    return min(len(DIFFICULTY_TIERS) - 1, tier + min(1, semantic_boost))


def _result_counts(result: Mapping[str, Any]) -> tuple[int, int, int]:
    confirmed = max(0, int(result.get("confirmed_defects", 0) or 0))
    found = max(0, int(result.get("confirmed_defects_found", 0) or 0))
    false_positives = max(0, int(result.get("false_positives", 0) or 0))
    return confirmed, min(found, confirmed), false_positives


def performance_window(results: Sequence[Mapping[str, Any]], *, size: int = MIN_PROMOTION_SAMPLES) -> dict[str, Any]:
    window = list(results[-max(1, int(size)):])
    confirmed = found = false_positives = 0
    integrity_complete = bool(window)
    for result in window:
        row_confirmed, row_found, row_false_positives = _result_counts(result)
        confirmed += row_confirmed
        found += row_found
        false_positives += row_false_positives
        integrity_complete = integrity_complete and result.get("provenance_complete") is True
        integrity_complete = integrity_complete and result.get("evidence_integrity") is True

    recall = found / confirmed if confirmed else 0.0
    reviewed_claims = found + false_positives
    false_positive_rate = false_positives / reviewed_claims if reviewed_claims else 0.0
    return {
        "sample_count": len(window),
        "confirmed_defects": confirmed,
        "confirmed_defects_found": found,
        "false_positives": false_positives,
        "recall": recall,
        "false_positive_rate": false_positive_rate,
        "integrity_complete": integrity_complete,
    }


def next_difficulty_tier(current_tier: int, recent_results: Sequence[Mapping[str, Any]]) -> int:
    """Promote one tier only after a complete, low-noise evidence window."""

    current = max(0, min(len(DIFFICULTY_TIERS) - 1, int(current_tier)))
    metrics = performance_window(recent_results)
    qualified = (
        metrics["sample_count"] >= MIN_PROMOTION_SAMPLES
        and metrics["confirmed_defects"] > 0
        and metrics["recall"] >= PROMOTION_RECALL
        and metrics["false_positive_rate"] <= MAX_FALSE_POSITIVE_RATE
        and metrics["integrity_complete"] is True
    )
    return min(len(DIFFICULTY_TIERS) - 1, current + 1) if qualified else current


def _language_allowed(language: str, history: Sequence[str]) -> bool:
    normalized_history = [normalize_language(item) for item in history]
    if normalized_history and normalized_history[-1] == language:
        return False

    recent_ten = normalized_history[-RUST_WINDOW:]
    if language == "rust" and recent_ten.count("rust") >= MAX_RUST_PER_WINDOW:
        return False

    recent_families = [language_family(item) for item in normalized_history[-5:]]
    family = language_family(language)
    if recent_families.count(family) >= 2:
        return False
    return True


def human_equivalent_workers(candidate: Mapping[str, Any]) -> int:
    """Estimate ordinary worker need before the existing ten-times multiplier."""

    tier = repository_difficulty(candidate)
    workers = 2 + (tier * 2)
    if bool(candidate.get("cross_component")):
        workers += 1
    if bool(candidate.get("concurrency_or_lifecycle")):
        workers += 1
    if float(candidate.get("defect_novelty", 0.0) or 0.0) >= 0.75:
        workers += 1
    return max(2, min(12, workers))


def _candidate_rank(candidate: Mapping[str, Any], target_tier: int) -> tuple[Any, ...]:
    tier = repository_difficulty(candidate)
    return (
        tier - target_tier,
        -float(candidate.get("defect_novelty", 0.0) or 0.0),
        -int(candidate.get("changed_files", 0) or 0),
        str(candidate.get("repository") or ""),
    )


def select_multilingual_candidates(
    candidates: Iterable[Mapping[str, Any]],
    *,
    target_tier: int,
    language_history: Sequence[str],
    count: int = 3,
) -> list[dict[str, Any]]:
    """Choose a difficulty-matched set while enforcing language rotation.

    The selector fails closed rather than falling back to an easier repository.
    Once promotion is earned, the curriculum waits for target-tier-or-harder
    candidates.
    """

    required_tier = max(0, min(len(DIFFICULTY_TIERS) - 1, int(target_tier)))
    remaining = [
        dict(candidate)
        for candidate in candidates
        if candidate.get("provenance_complete") is True
        and repository_difficulty(candidate) >= required_tier
    ]
    selected: list[dict[str, Any]] = []
    history = [normalize_language(item) for item in language_history]

    while remaining and len(selected) < max(1, int(count)):
        remaining.sort(key=lambda item: _candidate_rank(item, required_tier))
        index = next(
            (
                position
                for position, item in enumerate(remaining)
                if _language_allowed(normalize_language(item.get("language")), history)
            ),
            None,
        )
        if index is None:
            break
        candidate = remaining.pop(index)
        language = normalize_language(candidate.get("language"))
        tier = repository_difficulty(candidate)
        human_workers = human_equivalent_workers(candidate)
        candidate.update({
            "language": language,
            "language_family": language_family(language),
            "difficulty_tier": tier,
            "difficulty_name": DIFFICULTY_TIERS[tier].name,
            "human_equivalent_workers": human_workers,
            "private_count": private_force_size(human_workers),
        })
        selected.append(candidate)
        history.append(language)
    return selected


def plan_curriculum_round(
    *,
    candidates: Iterable[Mapping[str, Any]],
    current_tier: int,
    recent_results: Sequence[Mapping[str, Any]],
    language_history: Sequence[str],
    count: int = 3,
) -> dict[str, Any]:
    """Build a replayable next-round plan without granting promotion authority."""

    target_tier = next_difficulty_tier(current_tier, recent_results)
    selected = select_multilingual_candidates(
        candidates,
        target_tier=target_tier,
        language_history=language_history,
        count=count,
    )
    metrics = performance_window(recent_results)
    return {
        "schema_version": CURRICULUM_SCHEMA_VERSION,
        "current_tier": max(0, min(len(DIFFICULTY_TIERS) - 1, int(current_tier))),
        "target_tier": target_tier,
        "target_difficulty": DIFFICULTY_TIERS[target_tier].name,
        "promotion_metrics": metrics,
        "language_policy": {
            "same_language_consecutively": False,
            "max_same_family_per_five": 2,
            "rust_window": RUST_WINDOW,
            "max_rust_per_window": MAX_RUST_PER_WINDOW,
        },
        "cases": selected,
        "candidate_shortfall": len(selected) < max(1, int(count)),
        "planned_private_count": sum(int(item["private_count"]) for item in selected),
        "authority": {
            "may_promote_lessons": False,
            "may_merge": False,
            "final_verdict": "Sergeant",
        },
    }
