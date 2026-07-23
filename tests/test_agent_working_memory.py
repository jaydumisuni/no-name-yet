from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_MEMORY = ROOT / "AGENTS.md"
CLAUDE_MEMORY = ROOT / "CLAUDE.md"
COPILOT_MEMORY = ROOT / ".github" / "copilot-instructions.md"
OPERATIONAL_CONTRACTS = ROOT / "main_review" / "operational_contracts.py"
ADAPTIVE_CURRICULUM = ROOT / "main_review" / "adaptive_curriculum.py"
TENFOLD_DOCTRINE = ROOT / "docs" / "50-tenfold-operating-doctrine.md"


def test_tenfold_method_has_agent_and_sergeant_applications() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "10-for-2 / tenfold method has two linked applications" in memory
    assert "any AI, chat, coding agent, or reviewer" in memory
    assert "core Sergeant operating law" in memory
    assert "fast code review and governed learning" in memory
    assert "Do not separate these meanings" in memory


def test_sergeant_private_force_scaling_is_canonical_memory() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "2 human-equivalent workers  → 20 privates" in memory
    assert "5 human-equivalent workers  → 50 privates" in memory
    assert "12 human-equivalent workers → 120 privates" in memory
    assert "It is not a ceiling" in memory
    assert "permanent officers" in memory
    assert "Sergeant remains final authority" in memory
    assert "Hermes does not command" in memory


def test_working_agents_mirror_the_tenfold_method_without_weakening_proof() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "one coordinating lead" in memory
    assert "assign distinct parallel specialist roles" in memory
    assert "cross-check results through independent evidence or review lanes" in memory
    assert "finish faster without sacrificing quality" in memory
    assert "never from skipping proof" in memory
    assert "Do not create duplicate noise" in memory


def test_memory_preserves_existing_sergeant_mechanism_without_duplicate_subsystem() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "The user's exact wording is the requirement" in memory
    assert "already the private-force scaling law" in memory
    assert "does not require inventing a second tenfold subsystem" in memory
    assert "automatic lesson promotion" in memory
    assert "automatic merge" in memory


def test_major_agent_entry_points_share_the_dual_doctrine() -> None:
    claude = CLAUDE_MEMORY.read_text(encoding="utf-8")
    copilot = COPILOT_MEMORY.read_text(encoding="utf-8")

    assert "[`AGENTS.md`](AGENTS.md)" in claude
    assert "[`AGENTS.md`](../AGENTS.md)" in copilot
    for text in (claude, copilot):
        assert "two linked applications" in text
        assert "one coordinating lead" in text
        assert "private-force law" in text
        assert "2" in text and "20" in text
        assert "5" in text and "50" in text
        assert "12" in text and "120" in text
        assert "not a ceiling" in text
        assert "duplicate tenfold subsystem" in text or "second tenfold subsystem" in text


def test_memory_matches_the_implemented_private_force_contract() -> None:
    contracts = OPERATIONAL_CONTRACTS.read_text(encoding="utf-8")
    curriculum = ADAPTIVE_CURRICULUM.read_text(encoding="utf-8")

    assert "PRIVATE_FORCE_MULTIPLIER = 10" in contracts
    assert "MINIMUM_PRIVATE_FORCE = 20" in contracts
    assert "return max(MINIMUM_PRIVATE_FORCE, human * PRIVATE_FORCE_MULTIPLIER)" in contracts
    assert '"private_force_multiplier": PRIVATE_FORCE_MULTIPLIER' in contracts
    assert '"private_count": private_count' in contracts
    assert "private_force_size(human_workers)" in curriculum
    assert '"planned_private_count": sum' in curriculum


def test_full_tenfold_doctrine_documents_review_learning_and_command_chain() -> None:
    doctrine = TENFOLD_DOCTRINE.read_text(encoding="utf-8")

    assert "a core Sergeant execution law" in doctrine
    assert "Owner\n→ Sergeant\n→ Cpl council\n→ permanent officers" in doctrine
    assert "2 human-equivalent workers  → 20 privates" in doctrine
    assert "rapid code review and rapid governed learning" in doctrine
    assert "Teacher, Prosecutor, Defender" in doctrine
    assert "Hermes does not command" in doctrine
