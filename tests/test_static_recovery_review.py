from __future__ import annotations

from pathlib import Path

from main_review.static_recovery_review import run_static_recovery_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_state_changing_json_setter_requires_strict_shape(tmp_path: Path) -> None:
    source = tmp_path / "policy.go"
    source.write_text(
        """
package client
func (c *Client) SetBucketPolicyJSON(ctx context.Context, bucket, policyJSON string) error {
    next := &policyDoc{}
    if err := json.Unmarshal([]byte(policyJSON), next); err != nil { return err }
    return c.putPolicyDoc(ctx, bucket, next)
}
        """,
        encoding="utf-8",
    )
    assert "permissive-structured-input-acceptance" in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )


def test_strict_json_setter_with_required_content_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "policy.go"
    source.write_text(
        """
package client
func (c *Client) SetBucketPolicyJSON(ctx context.Context, bucket, policyJSON string) error {
    decoder := json.NewDecoder(strings.NewReader(policyJSON))
    decoder.DisallowUnknownFields()
    next := &policyDoc{}
    if err := decoder.Decode(next); err != nil { return err }
    if len(next.Statement) == 0 { return ErrInvalidPolicy }
    return c.putPolicyDoc(ctx, bucket, next)
}
        """,
        encoding="utf-8",
    )
    assert "permissive-structured-input-acceptance" not in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )


def test_status_conflict_cannot_be_swallowed(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) setReady(ctx context.Context, obj *Thing) error {
    if err := r.Status().Update(ctx, obj); err != nil && !apierrors.IsConflict(err) {
        return err
    }
    return nil
}
        """,
        encoding="utf-8",
    )
    assert "swallowed-status-conflict" in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )


def test_status_conflict_retry_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) setReady(ctx context.Context, obj *Thing) error {
    return retry.RetryOnConflict(retry.DefaultRetry, func() error {
        latest := &Thing{}
        if err := r.Get(ctx, key, latest); err != nil { return err }
        latest.Status.Ready = true
        return r.Status().Update(ctx, latest)
    })
}
        """,
        encoding="utf-8",
    )
    assert "swallowed-status-conflict" not in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )


def test_failed_status_must_recover_on_successful_no_change_reconcile(tmp_path: Path) -> None:
    source = tmp_path / "team_controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) Reconcile(ctx context.Context) error {
    if providerErr != nil { team.Status.TeamStatus = TeamStateFailed }
    statusChanged, newStatus := team.ChangeCalculator(desired)
    if statusChanged {
        team.Status = *newStatus
    } else {
        if team.Status.TeamStatus == "" {
            team.Status.TeamStatus = TeamStateComplete
        }
    }
    return nil
}
        """,
        encoding="utf-8",
    )
    assert "persisted-failure-not-recovered" in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )


def test_failed_status_recovery_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "team_controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) Reconcile(ctx context.Context) error {
    if providerErr != nil { team.Status.TeamStatus = TeamStateFailed }
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
    assert "persisted-failure-not-recovered" not in _roots(
        run_static_recovery_review(tmp_path, [source.name])
    )
