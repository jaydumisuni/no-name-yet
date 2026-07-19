from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_10_review import run_static_transfer_10_review


SAVE_ROOT = "ui-save-mutates-local-state-without-persistence"
SHAPE_ROOT = "invalid-response-shape-silently-converted-to-empty-result"
AUTHORITY_ROOT = "process-wide-runtime-authority-reached-through-mutable-global"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_state_only_save_that_exits_edit_mode_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "PropertyTab.tsx"
    source.write_text(
        r'''
const unitsAPI = { list: async (projectId: number) => fetch(`/api/projects/${projectId}/units`) };

export function PropertyTab({ projectId }: { projectId: number }) {
  const handleEditSave = () => {
    if (editDraft) {
      setUnits(prev => prev.map(u => u.id === editDraft.id ? editDraft : u));
      setEditingUnitId(null);
      setEditDraft(null);
    }
  };
  return <button onClick={handleEditSave}>Save</button>;
}
''',
        encoding="utf-8",
    )
    assert SAVE_ROOT in _roots(run_static_transfer_10_review(tmp_path, ["PropertyTab.tsx"]))


def test_persisted_save_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "PropertyTab.tsx"
    source.write_text(
        r'''
export function PropertyTab({ projectId }: { projectId: number }) {
  const handleEditSave = async () => {
    if (!editDraft) return;
    const response = await authFetch(`/api/projects/${projectId}/units/${editDraft.id}`, {
      method: "PATCH",
      body: JSON.stringify(editDraft),
    });
    if (!response.ok) throw new Error("save failed");
    setUnits(prev => prev.map(u => u.id === editDraft.id ? editDraft : u));
    setEditingUnitId(null);
    setEditDraft(null);
  };
}
''',
        encoding="utf-8",
    )
    assert SAVE_ROOT not in _roots(run_static_transfer_10_review(tmp_path, ["PropertyTab.tsx"]))


def test_save_callback_boundary_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Editor.tsx"
    source.write_text(
        r'''
export function Editor({ onSave, recordId }) {
  const handleSave = () => {
    onSave(editDraft);
    setRecords(prev => prev.map(row => row.id === editDraft.id ? editDraft : row));
    setEditingRecordId(null);
    setEditDraft(null);
  };
}
''',
        encoding="utf-8",
    )
    assert SAVE_ROOT not in _roots(run_static_transfer_10_review(tmp_path, ["Editor.tsx"]))


def test_dart_invalid_remote_shape_returning_empty_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "trip_service.dart"
    source.write_text(
        r'''
Future<List<Map<String, dynamic>>> fetchTripItems(String tripDisplayId) async {
  final path = '/api/trips/$tripDisplayId/items';
  final body = await _apiClient.get(path);
  if (body is! List) return [];
  return List<Map<String, dynamic>>.from(body);
}
''',
        encoding="utf-8",
    )
    assert SHAPE_ROOT in _roots(run_static_transfer_10_review(tmp_path, ["trip_service.dart"]))


def test_dart_invalid_remote_shape_that_throws_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "trip_service.dart"
    source.write_text(
        r'''
Future<List<Map<String, dynamic>>> fetchTripItems(String tripDisplayId) async {
  final path = '/api/trips/$tripDisplayId/items';
  final body = await _apiClient.get(path);
  if (body is! List) {
    throw StateError('Unexpected trip items response type');
  }
  return List<Map<String, dynamic>>.from(body);
}
''',
        encoding="utf-8",
    )
    assert SHAPE_ROOT not in _roots(run_static_transfer_10_review(tmp_path, ["trip_service.dart"]))


def test_javascript_invalid_remote_shape_returning_empty_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "client.ts"
    source.write_text(
        r'''
export async function fetchItems() {
  const response = await fetch("/api/items");
  const body = await response.json();
  if (!Array.isArray(body)) return [];
  return body;
}
''',
        encoding="utf-8",
    )
    assert SHAPE_ROOT in _roots(run_static_transfer_10_review(tmp_path, ["client.ts"]))


def test_global_runtime_authority_used_by_factory_is_reported(tmp_path: Path) -> None:
    header = tmp_path / "CommandRegistry.h"
    header.write_text(
        r'''
class AudioEngine;
class CommandRegistry {
public:
  static void setAudioEngine(AudioEngine* engine);
  static AudioEngine* getAudioEngine();
};
''',
        encoding="utf-8",
    )
    implementation = tmp_path / "CommandRegistry.cpp"
    implementation.write_text(
        r'''
AudioEngine* s_audioEngine = nullptr;

void CommandRegistry::setAudioEngine(AudioEngine* engine) {
  s_audioEngine = engine;
}
AudioEngine* CommandRegistry::getAudioEngine() {
  return s_audioEngine;
}
void CommandRegistry::initialize() {
  reg.registerCommand("play", [](const auto&) {
    AudioEngine* engine = getAudioEngine();
    return std::make_unique<PlayCommand>(*engine);
  });
}
''',
        encoding="utf-8",
    )
    result = run_static_transfer_10_review(
        tmp_path,
        ["CommandRegistry.h", "CommandRegistry.cpp"],
    )
    assert AUTHORITY_ROOT in _roots(result)


def test_explicit_operation_context_is_clean(tmp_path: Path) -> None:
    header = tmp_path / "CommandRegistry.h"
    header.write_text(
        r'''
struct CommandContext {
  AudioEngine* engine = nullptr;
};
class CommandRegistry {
public:
  std::unique_ptr<ICommand> build(const Flags& flags, const CommandContext& context);
};
''',
        encoding="utf-8",
    )
    implementation = tmp_path / "CommandRegistry.cpp"
    implementation.write_text(
        r'''
void CommandRegistry::initialize() {
  reg.registerCommand("play", [](const auto&, const CommandContext& context) {
    if (!context.engine) return nullptr;
    return std::make_unique<PlayCommand>(*context.engine);
  });
}
''',
        encoding="utf-8",
    )
    result = run_static_transfer_10_review(
        tmp_path,
        ["CommandRegistry.h", "CommandRegistry.cpp"],
    )
    assert AUTHORITY_ROOT not in _roots(result)
