from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_MEMORY = ROOT / "AGENTS.md"
CLAUDE_MEMORY = ROOT / "CLAUDE.md"
COPILOT_MEMORY = ROOT / ".github" / "copilot-instructions.md"


def test_tenfold_method_is_an_execution_rule_not_product_architecture() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "10-for-2 / tenfold method is an execution rule for the agent doing the work" in memory
    assert "It is not a Sergeant product feature" in memory
    assert "one normal lead worker" in memory
    assert "spread the work across more parallel specialist roles" in memory
    assert "cross-check the results through independent review lanes" in memory
    assert "finish faster without sacrificing quality" in memory
    assert "Speed must come from parallel decomposition and clean coordination" in memory


def test_agent_memory_preserves_the_users_exact_scope_boundary() -> None:
    memory = AGENT_MEMORY.read_text(encoding="utf-8")

    assert "The user's exact wording is the requirement" in memory
    assert '"Use 10-for-2" means' in memory
    assert "It does **not** mean add another private-force implementation to Sergeant" in memory
    assert "It does **not** authorize extra features, models, agents, branches, workflows, or storage" in memory


def test_major_agent_entry_points_share_one_canonical_memory() -> None:
    claude = CLAUDE_MEMORY.read_text(encoding="utf-8")
    copilot = COPILOT_MEMORY.read_text(encoding="utf-8")

    assert "[`AGENTS.md`](AGENTS.md)" in claude
    assert "[`AGENTS.md`](../AGENTS.md)" in copilot
    for text in (claude, copilot):
        assert "one coordinating lead" in text
        assert "parallel" in text
        assert "cross-check" in text
        assert "without" in text
        assert "Sergeant" in text
        assert "product feature" in text
