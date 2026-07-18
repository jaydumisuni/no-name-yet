from __future__ import annotations

from pathlib import Path

from main_review.static_js_remote_state_review import run_static_js_remote_state_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_inline_remote_record_before_local_claim_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text(
        """
let liveCall = null;

function openJitsiModal() {
  connectToRoom(liveCall.roomName);
}

async function startBrotherhoodCall(profile) {
  const roomName = `room-${Date.now()}`;
  await setDoc(doc(db, 'meta', 'liveCall'), {
    active: true,
    roomName,
    startedByName: profile.name,
  });
  openJitsiModal();
}
        """,
        encoding="utf-8",
    )
    result = run_static_js_remote_state_review(tmp_path, ["app.js"])
    assert "local-state-not-established-before-await" in _roots(result)


def test_local_claim_before_remote_record_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text(
        """
let liveCall = null;

function openJitsiModal() {
  connectToRoom(liveCall.roomName);
}

async function startBrotherhoodCall(profile) {
  const roomName = `room-${Date.now()}`;
  const callData = { active: true, roomName, startedByName: profile.name };
  liveCall = callData;
  await setDoc(doc(db, 'meta', 'liveCall'), callData);
  openJitsiModal();
}
        """,
        encoding="utf-8",
    )
    result = run_static_js_remote_state_review(tmp_path, ["app.js"])
    assert "local-state-not-established-before-await" not in _roots(result)


def test_unrelated_remote_resource_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text(
        """
let liveCall = null;

function openJitsiModal() {
  connectToRoom(liveCall.roomName);
}

async function saveProfile(profile) {
  await setDoc(doc(db, 'profiles', profile.id), profile);
  openJitsiModal();
}
        """,
        encoding="utf-8",
    )
    result = run_static_js_remote_state_review(tmp_path, ["app.js"])
    assert "local-state-not-established-before-await" not in _roots(result)
