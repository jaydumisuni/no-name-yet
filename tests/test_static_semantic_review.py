from __future__ import annotations

from pathlib import Path

from main_review.external_static_review import run_external_static_review
from main_review.static_semantic_review import run_static_semantic_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_one_shot_try_lock_without_retry_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Task.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        class Task {
            void timeout() {
                if (lock.tryLock()) {
                    try { finish(); } finally { lock.unlock(); }
                }
            }
        }
        """,
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Task.java"])
    assert "one-shot-lock-loss" in _roots(result)


def test_one_shot_blocking_lock_or_reschedule_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Task.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        class Task {
            void timeout() {
                lock.lock();
                try { finish(); } finally { lock.unlock(); }
            }
            void deadline() {
                if (lock.tryLock()) {
                    try { finish(); } finally { lock.unlock(); }
                } else {
                    scheduler.schedule(this::deadline, 1, SECONDS);
                }
            }
        }
        """,
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Task.java"])
    assert "one-shot-lock-loss" not in _roots(result)


def test_keyboard_path_bypassing_canonical_submit_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Form.tsx"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        export function Form() {
          return <form onSubmit={async (event) => {
            event.preventDefault();
            if (shouldValidate) await validate(value);
            setError(null);
            setValue(value);
            if (clearOnSubmit) clear();
          }}>
            <div onKeyDown={(event) => {
              if (event.key === "Enter" && event.ctrlKey) {
                event.preventDefault();
                setValue(value);
              }
            }} />
          </form>;
        }
        """,
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Form.tsx"])
    assert "canonical-action-flow-bypass" in _roots(result)


def test_keyboard_path_using_request_submit_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Form.tsx"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        export function Form() {
          return <form ref={formRef} onSubmit={async (event) => {
            event.preventDefault();
            if (shouldValidate) await validate(value);
            setError(null);
            setValue(value);
            if (clearOnSubmit) clear();
          }}>
            <div onKeyDown={(event) => {
              if (event.key === "Enter" && event.ctrlKey) {
                event.preventDefault();
                formRef.current?.requestSubmit();
              }
            }} />
          </form>;
        }
        """,
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Form.tsx"])
    assert "canonical-action-flow-bypass" not in _roots(result)


def test_event_publication_before_state_initialization_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Store.ts"
    listener = tmp_path / "src" / "Listener.ts"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        class Store {
          private async saveKey(key: Key): Promise<void> {
            await db.save(key);
            this.emit(CryptoEvent.KeyCached, key);
          }
          public async createBackup(): Promise<void> {
            const created = await api.postBackup();
            await this.saveKey(created.key);
          }
        }
        """,
        encoding="utf-8",
    )
    listener.write_text(
        "client.on(CryptoEvent.KeyCached, () => client.readActiveBackupState());\n",
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Store.ts"])
    assert "publication-before-initialization" in _roots(result)


def test_event_publication_after_state_initialization_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Store.ts"
    listener = tmp_path / "src" / "Listener.ts"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
        class Store {
          private async saveKey(key: Key): Promise<void> {
            await db.save(key);
            this.emit(CryptoEvent.KeyCached, key);
          }
          public async createBackup(): Promise<void> {
            const created = await api.postBackup();
            this.serverBackupInfo = created.info;
            await this.enableBackup(created.info);
            await this.saveKey(created.key);
          }
        }
        """,
        encoding="utf-8",
    )
    listener.write_text(
        "client.on(CryptoEvent.KeyCached, () => client.readActiveBackupState());\n",
        encoding="utf-8",
    )
    result = run_static_semantic_review(tmp_path, ["src/Store.ts"])
    assert "publication-before-initialization" not in _roots(result)


def test_external_static_policy_does_not_gate_unrelated_repository_secret_or_release_standard(tmp_path: Path) -> None:
    changed = tmp_path / "src" / "feature.ts"
    unrelated = tmp_path / "src" / "old.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("export function feature() { return true; }\n", encoding="utf-8")
    unrelated.write_text('const api_key = "abcdefghijklmnop";\n', encoding="utf-8")
    result = run_external_static_review(tmp_path, ["src/feature.ts", "tests/future.spec.ts"])
    assert result["policy_profile"] == "external_static"
    assert result["standard"]["blockers"] == []
    assert result["unavailable_requested_files"] == ["tests/future.spec.ts"]
    assert all(item.get("path") != "src/old.ts" for item in result["officer_council"]["admitted_findings"])
