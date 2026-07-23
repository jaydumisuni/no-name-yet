from __future__ import annotations

from pathlib import Path

from main_review.operational_contracts import (
    MINIMUM_PRIVATE_FORCE,
    PRIVATE_FORCE_MULTIPLIER,
    private_force_size,
)


ROOT = Path(__file__).resolve().parents[1]
AGENT_MEMORY = ROOT / "AGENTS.md"
CLAUDE_MEMORY = ROOT / "CLAUDE.md"
COPILOT_MEMORY = ROOT / ".github" / "copilot-instructions.md"


def test_tenfold_method_is_core_sergeant_architecture_and_agent_method() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "10-for-2 / tenfold method is a core Sergeant operating law" in memory
    assert "also the working method agents should mirror" in memory
    assert "It is not merely a prompt-writing shortcut" in memory
    assert "Sergeant's speed in code review and controlled learning depends" in memory
    assert "private force = normally justified human-equivalent workers × 10" in memory
    assert "finish faster without sacrificing quality" in memory


def test_private_force_law_remains_tenfold_with_twenty_minimum_not_ceiling() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert PRIVATE_FORCE_MULTIPLIER == 10
    assert MINIMUM_PRIVATE_FORCE == 20
    assert private_force_size(1) == 20
    assert private_force_size(2) == 20
    assert private_force_size(5) == 50
    assert private_force_size(12) == 120
    assert "Twenty is the minimum meaningful private formation" in memory
    assert "it is not a mission ceiling" in memory
    assert "another bounded private cell" in memory


def test_memory_preserves_sergeant_command_hierarchy() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")
    normalized = memory.lower()

    assert "sergeant defines the mission, proof gates, and final verdict" in normalized
    assert "cpl is the reasoning council and commands the operation" in normalized
    assert "permanent officers own specialist missions" in normalized
    assert "private packets cannot expand scope or issue verdicts" in normalized
    assert "hermes transports orders, evidence, and preserved learning packets" in normalized
    assert "hermes does not command" in normalized


def test_cross_repository_learning_is_allowed_but_governed() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "any useful repository" in memory
    assert "including THETECHGUY projects and external repositories" in memory
    assert "not only changes made inside the Sergeant repository" in memory
    assert "defective commit or reproducible failing state" in memory
    assert "fixing commit or independently verified correction" in memory
    assert "freeze Sergeant's blind result" in memory
    assert "unrelated-language or unrelated-repository transfer" in memory
    assert "routine commit notification, shell transcript, successful build" in memory
    assert "is not automatically a lesson" in memory
    assert "No lesson is automatically promoted" in memory


def test_major_agent_entry_points_share_the_full_doctrine() -> None:
    claude = CLAUDE_MEMORY.read_text(encoding="utf-8")
    copilot = COPILOT_MEMORY.read_text(encoding="utf-8")

    assert "[`AGENTS.md`](AGENTS.md)" in claude
    assert "[`AGENTS.md`](../AGENTS.md)" in copilot
    for text in (claude, copilot):
        normalized = text.lower()
        assert "core sergeant" in normalized
        assert "cpl" in normalized
        assert "officers" in normalized
        assert "privates" in normalized
        assert "2" in text and "20" in text
        assert "external repository" in normalized
        assert "no automatic" in normalized or "no lesson is automatically" in normalized
        assert "parallel" in normalized
        assert "cross-check" in normalized or "verification" in normalized
