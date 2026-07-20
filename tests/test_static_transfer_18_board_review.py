from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_18_review import run_static_transfer_18_review


ROOT = "install-path-trusts-stale-sidecar-without-yaml-authority-check"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_live_yaml_and_sidecar_board_require_consistency_gate(tmp_path: Path) -> None:
    source = tmp_path / "device.ts"
    source.write_text(
        '''
class DevicePage {
  private _yaml = "";
  private get _device() { return this._devices.find((d) => d.configuration === this.id); }
  private _firmwareDialog!: FirmwareInstallDialog;
  private install() {
    const board = this._device?.board_id;
    this._firmwareDialog.open(this.id, board);
  }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["device.ts"])

    assert ROOT in _roots(result)


def test_unrelated_manual_board_change_does_not_prove_install_consistency(tmp_path: Path) -> None:
    source = tmp_path / "device.ts"
    source.write_text(
        '''
class DevicePage {
  private _yaml = "";
  private get _device() { return this._devices.find((d) => d.configuration === this.id); }
  private _firmwareDialog!: FirmwareInstallDialog;
  private install() {
    this._firmwareDialog.open(this.id, this._device?.board_id);
  }
  private openManualBoardPicker() {
    this.dispatchEvent(new CustomEvent("request-change-board"));
  }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["device.ts"])

    assert ROOT in _roots(result)


def test_yaml_board_id_comment_does_not_prove_runtime_comparison(tmp_path: Path) -> None:
    source = tmp_path / "device.ts"
    source.write_text(
        '''
class DevicePage {
  private _yaml = "";
  private get _device() { return this._devices.find((d) => d.configuration === this.id); }
  private _firmwareDialog!: FirmwareInstallDialog;
  // YAML is loaded when board_id changes, but this is not an install-time mismatch check.
  private install() {
    this._firmwareDialog.open(this.id, this._device?.board_id);
  }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["device.ts"])

    assert ROOT in _roots(result)


def test_yaml_board_mismatch_guard_and_reselect_are_clean(tmp_path: Path) -> None:
    source = tmp_path / "device.ts"
    source.write_text(
        '''
class DevicePage {
  private _yaml = "";
  private get _device() { return this._devices.find((d) => d.configuration === this.id); }
  private _firmwareDialog!: FirmwareInstallDialog;
  private install() {
    const parsed = readPlatformBoard(this._yaml);
    if (boardDisagrees(parsed, this._device?.board_id)) {
      this.dispatchEvent(new CustomEvent("request-change-board"));
      return;
    }
    this._firmwareDialog.open(this.id, this._device?.board_id);
  }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["device.ts"])

    assert ROOT not in _roots(result)


def test_install_with_single_board_authority_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "device.ts"
    source.write_text(
        '''
class DevicePage {
  private _firmwareDialog!: FirmwareInstallDialog;
  private install(boardId: string) {
    this._firmwareDialog.open(this.id, boardId);
  }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["device.ts"])

    assert ROOT not in _roots(result)
