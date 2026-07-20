from __future__ import annotations

from pathlib import Path

from main_review.static_status_review import run_static_status_review
from main_review.static_transfer_21_review import run_static_transfer_21_review


ROOT = "contract-result-field-discarded-by-adapter-default"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def _contract() -> str:
    return """
public record struct ThreadData(
    uint Id,
    nuint OSId,
    ThreadState State,
    bool PreemptiveGCDisabled);
"""


def test_adapter_discards_populated_contract_field_with_default(tmp_path: Path) -> None:
    _write(tmp_path, "Contracts.cs", _contract())
    _write(
        tmp_path,
        "LegacyAdapter.cs",
        """
unsafe class LegacyAdapter {
    int GetThreadData(Address thread, Output* data) {
        Contracts.ThreadData threadData = contract.GetThreadData(thread);
        data->id = (int)threadData.Id;
        data->osId = (int)threadData.OSId;
        data->state = 0;
        data->preemptive = threadData.PreemptiveGCDisabled ? 1 : 0;
        return 0;
    }
}
""",
    )

    result = run_static_transfer_21_review(
        tmp_path,
        ["Contracts.cs", "LegacyAdapter.cs"],
    )

    assert ROOT in _roots(result)


def test_adapter_forwards_contract_field_is_clean(tmp_path: Path) -> None:
    _write(tmp_path, "Contracts.cs", _contract())
    _write(
        tmp_path,
        "LegacyAdapter.cs",
        """
unsafe class LegacyAdapter {
    int GetThreadData(Address thread, Output* data) {
        Contracts.ThreadData threadData = contract.GetThreadData(thread);
        data->id = (int)threadData.Id;
        data->osId = (int)threadData.OSId;
        data->state = (int)threadData.State;
        data->preemptive = threadData.PreemptiveGCDisabled ? 1 : 0;
        return 0;
    }
}
""",
    )

    result = run_static_transfer_21_review(
        tmp_path,
        ["Contracts.cs", "LegacyAdapter.cs"],
    )

    assert ROOT not in _roots(result)


def test_default_output_without_matching_contract_field_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Contracts.cs",
        """
public record struct ThreadData(
    uint Id,
    nuint OSId,
    bool PreemptiveGCDisabled);
""",
    )
    _write(
        tmp_path,
        "LegacyAdapter.cs",
        """
unsafe class LegacyAdapter {
    int GetThreadData(Address thread, Output* data) {
        Contracts.ThreadData threadData = contract.GetThreadData(thread);
        data->id = (int)threadData.Id;
        data->osId = (int)threadData.OSId;
        data->state = 0;
        data->preemptive = threadData.PreemptiveGCDisabled ? 1 : 0;
        return 0;
    }
}
""",
    )

    result = run_static_transfer_21_review(
        tmp_path,
        ["Contracts.cs", "LegacyAdapter.cs"],
    )

    assert ROOT not in _roots(result)


def test_isolated_default_initialization_is_clean(tmp_path: Path) -> None:
    _write(tmp_path, "Contracts.cs", _contract())
    _write(
        tmp_path,
        "LegacyAdapter.cs",
        """
unsafe class LegacyAdapter {
    int Initialize(Output* data) {
        data->state = 0;
        return 0;
    }
}
""",
    )

    result = run_static_transfer_21_review(
        tmp_path,
        ["Contracts.cs", "LegacyAdapter.cs"],
    )

    assert ROOT not in _roots(result)


def test_normal_static_status_path_admits_transfer_21_root(tmp_path: Path) -> None:
    _write(tmp_path, "Contracts.cs", _contract())
    _write(
        tmp_path,
        "LegacyAdapter.cs",
        """
unsafe class LegacyAdapter {
    int GetThreadData(Address thread, Output* data) {
        Contracts.ThreadData threadData = contract.GetThreadData(thread);
        data->id = (int)threadData.Id;
        data->osId = (int)threadData.OSId;
        data->state = 0;
        data->preemptive = threadData.PreemptiveGCDisabled ? 1 : 0;
        return 0;
    }
}
""",
    )

    result = run_static_status_review(
        tmp_path,
        ["Contracts.cs", "LegacyAdapter.cs"],
    )

    assert ROOT in _roots(result)
