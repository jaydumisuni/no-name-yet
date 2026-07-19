from __future__ import annotations

from pathlib import Path

from main_review.static_contract_surface_review import run_static_contract_surface_review
from main_review.static_status_review import run_static_status_review


UI_ROOT = "ui-save-mutates-local-state-without-persistence"
SHAPE_ROOT = "remote-collection-contract-violation-collapsed-to-empty"
AUTHORITY_ROOT = "process-wide-runtime-authority-reached-through-mutable-global"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_state_only_ui_save_that_exits_edit_mode_is_collapsed_to_one_root(tmp_path: Path) -> None:
    source = tmp_path / "PropertyTab.tsx"
    source.write_text(
        """
import { unitsAPI } from "./api";
const projectId = "p1";

const handlePlanEditSave = () => {
  if (planEditDraft) {
    setFloorPlans(prev =>
      prev.map(plan => plan.id === planEditDraft.id ? planEditDraft : plan)
    );
    setEditingPlanId(null);
    setPlanEditDraft(null);
  }
};

const handleEditSave = () => {
  if (editDraft) {
    setUnits(prev => prev.map(unit => unit.id === editDraft.id ? editDraft : unit));
    setEditingUnitId(null);
    setEditDraft(null);
  }
};
        """,
        encoding="utf-8",
    )

    result = run_static_contract_surface_review(tmp_path, ["PropertyTab.tsx"])

    findings = [item for item in result["findings"] if item["root_cause"] == UI_ROOT]
    assert len(findings) == 1
    assert findings[0]["severity"] == "major"


def test_persisted_ui_save_that_stays_open_on_failure_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "PropertyTab.tsx"
    source.write_text(
        """
const projectId = "p1";
const handlePlanEditSave = async () => {
  if (!planEditDraft) return;
  const response = await fetch(`/api/plans/${planEditDraft.id}`, {
    method: "PATCH",
    body: JSON.stringify(planEditDraft),
  });
  if (!response.ok) {
    setSaveError(await response.text());
    return;
  }
  setFloorPlans(prev =>
    prev.map(plan => plan.id === planEditDraft.id ? planEditDraft : plan)
  );
  setEditingPlanId(null);
  setPlanEditDraft(null);
};
        """,
        encoding="utf-8",
    )

    result = run_static_contract_surface_review(tmp_path, ["PropertyTab.tsx"])

    assert UI_ROOT not in _roots(result)


def test_editor_cancel_is_not_misclassified_as_save(tmp_path: Path) -> None:
    source = tmp_path / "PropertyTab.tsx"
    source.write_text(
        """
const handlePlanEditCancel = () => {
  setEditingPlanId(null);
  setPlanEditDraft(null);
};
        """,
        encoding="utf-8",
    )

    result = run_static_contract_surface_review(tmp_path, ["PropertyTab.tsx"])

    assert UI_ROOT not in _roots(result)


def test_remote_collection_contract_is_owned_by_canonical_remote_officer(tmp_path: Path) -> None:
    source = tmp_path / "trip_service.dart"
    source.write_text(
        """
class TripService {
  final ApiClient _apiClient;

  Future<List<Map<String, dynamic>>> fetchTripItems(String tripId) async {
    final body = await _apiClient.get('/api/trips/$tripId/items');
    if (body is! List) return const [];
    return List<Map<String, dynamic>>.from(body);
  }
}
        """,
        encoding="utf-8",
    )

    result = run_static_status_review(tmp_path, ["trip_service.dart"])

    assert SHAPE_ROOT in _roots(result)
    assert result["static_remote_contract_review"]["finding_count"] == 1
    assert result["static_contract_surface_review"]["finding_count"] == 0


def test_remote_collection_contract_throwing_typed_error_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "trip_service.dart"
    source.write_text(
        """
class TripService {
  final ApiClient _apiClient;

  Future<List<Map<String, dynamic>>> fetchTripItems(String tripId) async {
    final body = await _apiClient.get('/api/trips/$tripId/items');
    if (body is! List) {
      throw StateError('Unexpected trip items response type');
    }
    return List<Map<String, dynamic>>.from(body);
  }
}
        """,
        encoding="utf-8",
    )

    result = run_static_status_review(tmp_path, ["trip_service.dart"])

    assert SHAPE_ROOT not in _roots(result)


def test_command_registry_process_global_runtime_authority_is_reported(tmp_path: Path) -> None:
    header = tmp_path / "CommandRegistry.h"
    header.write_text(
        """
class AudioEngine;
class CommandRegistry {
public:
  using Factory = int;
  static void setAudioEngine(AudioEngine* engine);
  static AudioEngine* getAudioEngine();
};
        """,
        encoding="utf-8",
    )
    implementation = tmp_path / "CommandRegistry.cpp"
    implementation.write_text(
        """
AudioEngine* s_audioEngine = nullptr;
void CommandRegistry::setAudioEngine(AudioEngine* engine) { s_audioEngine = engine; }
AudioEngine* CommandRegistry::getAudioEngine() { return s_audioEngine; }
void CommandRegistry::initialize() {
  reg.registerCommand("play", [] { return getAudioEngine() != nullptr; });
}
        """,
        encoding="utf-8",
    )

    result = run_static_contract_surface_review(
        tmp_path,
        ["CommandRegistry.h", "CommandRegistry.cpp"],
    )

    assert AUTHORITY_ROOT in _roots(result)


def test_explicit_per_build_context_is_clean(tmp_path: Path) -> None:
    header = tmp_path / "CommandRegistry.h"
    header.write_text(
        """
struct CommandContext { AudioEngine* engine; };
class CommandRegistry {
public:
  using Factory = int;
  int build(const Flags& flags, const CommandContext& context);
};
        """,
        encoding="utf-8",
    )
    implementation = tmp_path / "CommandRegistry.cpp"
    implementation.write_text(
        """
void CommandRegistry::initialize() {
  reg.registerCommand("play", [](const auto&, const CommandContext& context) {
    return context.engine ? 1 : 0;
  });
}
        """,
        encoding="utf-8",
    )

    result = run_static_contract_surface_review(
        tmp_path,
        ["CommandRegistry.h", "CommandRegistry.cpp"],
    )

    assert AUTHORITY_ROOT not in _roots(result)


def test_status_bundle_exposes_one_root_per_transfer_10_obligation(tmp_path: Path) -> None:
    ui = tmp_path / "PropertyTab.tsx"
    ui.write_text(
        """
const projectId = "p1";
const handleEditSave = () => {
  setUnits(prev => prev.map(unit => unit.id === editDraft.id ? editDraft : unit));
  setEditingUnitId(null);
  setEditDraft(null);
};
        """,
        encoding="utf-8",
    )
    dart = tmp_path / "trip_service.dart"
    dart.write_text(
        """
class TripService {
  final ApiClient _apiClient;
  Future<List<Map<String, dynamic>>> fetchTripItems(String id) async {
    final body = await _apiClient.get('/items');
    if (body is! List) return const [];
    return List<Map<String, dynamic>>.from(body);
  }
}
        """,
        encoding="utf-8",
    )
    header = tmp_path / "CommandRegistry.h"
    header.write_text(
        """
class CommandRegistry {
public:
  using Factory = int;
  static void setAudioEngine(AudioEngine* engine);
  static AudioEngine* getAudioEngine();
};
        """,
        encoding="utf-8",
    )
    implementation = tmp_path / "CommandRegistry.cpp"
    implementation.write_text(
        """
AudioEngine* s_audioEngine = nullptr;
void CommandRegistry::setAudioEngine(AudioEngine* engine) { s_audioEngine = engine; }
AudioEngine* CommandRegistry::getAudioEngine() { return s_audioEngine; }
void CommandRegistry::initialize() {
  reg.registerCommand("play", [] { return getAudioEngine() != nullptr; });
}
        """,
        encoding="utf-8",
    )

    result = run_static_status_review(
        tmp_path,
        [
            "PropertyTab.tsx",
            "trip_service.dart",
            "CommandRegistry.h",
            "CommandRegistry.cpp",
        ],
    )

    roots = _roots(result)
    assert {UI_ROOT, SHAPE_ROOT, AUTHORITY_ROOT}.issubset(roots)
    assert result["static_contract_surface_review"]["finding_count"] == 2
    assert result["static_remote_contract_review"]["finding_count"] == 1
