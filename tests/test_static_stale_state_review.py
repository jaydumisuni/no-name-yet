from __future__ import annotations

from pathlib import Path

from main_review.static_stale_state_review import run_static_stale_state_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_large_reconciler_recovers_failed_state_in_no_change_branch(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    noise = "\n".join(f"    // unrelated reconciliation stage {index}" for index in range(800))
    source.write_text(
        f"""
package controller
func (r *Reconciler) Reconcile(ctx context.Context) error {{
    if providerErr != nil {{
        team.Status.TeamStatus = TeamStateFailed
        team.Status.TeamStatusError = providerErr.Error()
    }}
{noise}
    statusChanged, newStatus := team.ChangeCalculator(desired)
    if statusChanged {{
        retry.RetryOnConflict(retry.DefaultRetry, func() error {{
            latest := &Team{{}}
            latest.Status = *newStatus
            return r.Status().Update(ctx, latest)
        }})
    }} else {{
        if team.Status.TeamStatus == "" {{
            team.Status.TeamStatus = TeamStateComplete
        }}
    }}
    return nil
}}
        """,
        encoding="utf-8",
    )
    result = run_static_stale_state_review(tmp_path, [source.name])
    assert "persisted-failure-not-recovered" in _roots(result)


def test_nested_no_change_branch_that_recovers_failed_state_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) Reconcile(ctx context.Context) error {
    if providerErr != nil {
        team.Status.TeamStatus = TeamStateFailed
        team.Status.TeamStatusError = providerErr.Error()
    }
    statusChanged, newStatus := team.ChangeCalculator(desired)
    if statusChanged {
        team.Status = *newStatus
    } else {
        if team.Status.TeamStatus == "" || team.Status.TeamStatus == TeamStateFailed {
            team.Status.TeamStatus = TeamStateComplete
            team.Status.TeamStatusError = ""
        }
    }
    return nil
}
        """,
        encoding="utf-8",
    )
    result = run_static_stale_state_review(tmp_path, [source.name])
    assert "persisted-failure-not-recovered" not in _roots(result)
