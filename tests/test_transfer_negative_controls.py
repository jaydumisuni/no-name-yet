from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_review import run_static_transfer_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_unscoped_api_key_without_permission_contract_is_not_reported(tmp_path: Path) -> None:
    handler = tmp_path / "handler.go"
    auth = tmp_path / "apikey.go"
    handler.write_text(
        """
package api
func (h *Handler) requirePermission(ctx context.Context, req *Request) error {
    apiKey := extractAPIKey(req)
    if h.checkAdminAPIKey(apiKey) { return nil }
    token := h.extractBearerToken(req)
    if token == "" { return NewClientError(401, "missing token") }
    return nil
}
        """,
        encoding="utf-8",
    )
    auth.write_text(
        """
package auth
func (s *Service) ValidateUserAPIKeyAPI(ctx context.Context, key string) error {
    return s.ValidateUserAPIKey(ctx, key)
}
        """,
        encoding="utf-8",
    )

    assert "credential-scope-not-enforced" not in _roots(
        run_static_transfer_review(tmp_path, [handler.name, auth.name])
    )


def test_level_triggered_reconcile_notfound_is_not_one_shot_status_loss(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    source.write_text(
        """
package controller
func (r *Reconciler) syncRouteStatus(ctx context.Context) error {
    return retry.Do(func() error {
        route, err := r.Get(ctx, key)
        if err != nil {
            if apierrors.IsNotFound(err) { return nil }
            return err
        }
        status := report.BuildRouteStatus(ctx, route)
        route.Status = *status
        return r.Status().Update(ctx, route)
    })
}
        """,
        encoding="utf-8",
    )

    assert "transient-cache-notfound-drops-status" not in _roots(
        run_static_transfer_review(tmp_path, [source.name])
    )


def test_disposable_test_database_initialization_is_not_rebuild_loss(tmp_path: Path) -> None:
    source = tmp_path / "fixture.py"
    source.write_text(
        """
import sqlite3

def make_test_database(db_path):
    if db_path.exists():
        db_path.unlink()
    return sqlite3.connect(db_path)
        """,
        encoding="utf-8",
    )

    assert "destructive-in-place-rebuild" not in _roots(
        run_static_transfer_review(tmp_path, [source.name])
    )
