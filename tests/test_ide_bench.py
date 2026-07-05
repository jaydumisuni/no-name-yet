from __future__ import annotations

from sergeant import main as sergeant_main
from main_review.cli import main
from main_review.ide_bench import build_ide_bench_contract
from main_review.review_contract import CONTRACT_VERSION


def test_ide_bench_contract_locks_interfaces_and_handoff() -> None:
    payload = build_ide_bench_contract()

    assert payload["ok"] is True
    assert payload["schema_version"] == CONTRACT_VERSION
    assert payload["interfaces"]["vscode"]["request_format"] == CONTRACT_VERSION
    assert payload["interfaces"]["vscode"]["icon_asset"] == "resources/srg-logo-and-icon.png"
    assert payload["interfaces"]["pycharm"]["name"] == "PyCharm"
    assert payload["interfaces"]["pycharm"]["vendor_family"] == "JetBrains"
    assert payload["interfaces"]["pycharm"]["icon_asset"] == "resources/srg-logo-and-icon.png"
    assert payload["interfaces"]["jetbrains"]["response_format"] == CONTRACT_VERSION
    assert payload["interfaces"]["jetbrains"]["icon_asset"] == "resources/srg-logo-and-icon.png"
    assert payload["ai_handoff_contract"]["schema_version"] == CONTRACT_VERSION
    assert "Review Pull Request" in payload["interfaces"]["vscode"]["minimum_commands"]
    assert "Review Pull Request" in payload["interfaces"]["pycharm"]["minimum_actions"]
    assert "Review Pull Request" in payload["interfaces"]["jetbrains"]["minimum_actions"]


def test_ide_bench_cli_runs() -> None:
    assert main(["ide-bench-contract"]) == 0


def test_ide_launcher_runs_same_cli() -> None:
    assert sergeant_main(["ide-bench-contract"]) == 0
