from __future__ import annotations

from pathlib import Path

from main_review.static_terminal_state_review import run_static_terminal_state_review


ROOT = "nonterminal-progress-can-overwrite-terminal-state"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_progress_update_without_terminal_guard_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "store.go"
    source.write_text(
        r'''
package store

var statuses = []string{"running", "completed", "failed", "cancelled", "interrupted"}

func (s *Store) UpdateBatchProgress(ctx context.Context, row BatchRow) error {
    _, err := s.db.ExecContext(ctx, `
        UPDATE batches
           SET status = ?, processed_files = ?, failed_files = ?, updated_at = ?
         WHERE id = ?
    `, row.Status, row.Processed, row.Failed, row.UpdatedAt, row.ID)
    return err
}
''',
        encoding="utf-8",
    )
    result = run_static_terminal_state_review(tmp_path, ["store.go"])
    assert ROOT in _roots(result)


def test_progress_update_with_terminal_predicate_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "store.go"
    source.write_text(
        r'''
package store

var statuses = []string{"running", "completed", "failed", "cancelled", "interrupted"}

func (s *Store) UpdateBatchProgress(ctx context.Context, row BatchRow) error {
    _, err := s.db.ExecContext(ctx, `
        UPDATE batches
           SET status = ?, processed_files = ?, failed_files = ?, updated_at = ?
         WHERE id = ?
           AND status NOT IN ('completed', 'failed', 'cancelled', 'interrupted')
    `, row.Status, row.Processed, row.Failed, row.UpdatedAt, row.ID)
    return err
}
''',
        encoding="utf-8",
    )
    result = run_static_terminal_state_review(tmp_path, ["store.go"])
    assert ROOT not in _roots(result)


def test_deliberate_status_only_transition_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "store.go"
    source.write_text(
        r'''
package store

var statuses = []string{"running", "completed", "failed", "cancelled"}

func (s *Store) UpdateBatchStatus(ctx context.Context, row BatchRow) error {
    _, err := s.db.ExecContext(ctx, `
        UPDATE batches SET status = ?, updated_at = ? WHERE id = ?
    `, row.Status, row.UpdatedAt, row.ID)
    return err
}
''',
        encoding="utf-8",
    )
    result = run_static_terminal_state_review(tmp_path, ["store.go"])
    assert ROOT not in _roots(result)
