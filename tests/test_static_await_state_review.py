from __future__ import annotations

from pathlib import Path

from main_review.static_await_state_review import run_static_await_state_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_python_stale_snapshot_persisted_after_await_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
async def refresh():
    state = load_data()
    remote = await fetch_remote()
    state["temperature"] = remote["temperature"]
    save_data(state)
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["worker.py"])
    assert "stale-snapshot-persisted-after-await" in _roots(result)


def test_python_reload_after_await_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
async def refresh():
    state = load_data()
    remote = await fetch_remote()
    state = load_data()
    state["temperature"] = remote["temperature"]
    save_data(state)
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["worker.py"])
    assert "stale-snapshot-persisted-after-await" not in _roots(result)


def test_javascript_shared_state_consumed_after_remote_await_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text(
        """
let liveCall = null;

function openCallModal() {
  renderRoom(liveCall.roomName);
}

async function startCall() {
  const callData = { roomName: makeRoomName() };
  await saveRemote(callData);
  openCallModal();
}
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["app.js"])
    assert "local-state-not-established-before-await" in _roots(result)


def test_javascript_shared_state_committed_before_await_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text(
        """
let liveCall = null;

function openCallModal() {
  renderRoom(liveCall.roomName);
}

async function startCall() {
  const callData = { roomName: makeRoomName() };
  liveCall = callData;
  await saveRemote(callData);
  openCallModal();
}
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["app.js"])
    assert "local-state-not-established-before-await" not in _roots(result)


def test_typescript_shared_reset_before_await_and_append_after_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Sidebar.tsx"
    source.write_text(
        """
const loadCollections = async () => {
  collections.value = [];
  const data = await api.getCalendars();
  collections.value = [...collections.value, ...data.calendars];
};
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["Sidebar.tsx"])
    assert "shared-state-reset-before-await-mutation" in _roots(result)


def test_typescript_call_local_accumulation_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Sidebar.tsx"
    source.write_text(
        """
const loadCollections = async () => {
  const nextCollections = [];
  const data = await api.getCalendars();
  nextCollections.push(...data.calendars);
  collections.value = nextCollections;
};
        """,
        encoding="utf-8",
    )
    result = run_static_await_state_review(tmp_path, ["Sidebar.tsx"])
    assert "shared-state-reset-before-await-mutation" not in _roots(result)
