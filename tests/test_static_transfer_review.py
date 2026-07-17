from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_review import run_static_transfer_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_one_shot_status_report_that_accepts_notfound_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "status_syncer.go"
    source.write_text(
        """
package syncer
func (s *StatusSyncer) Start(ctx context.Context) error {
    report, _ := s.reportQueue.Dequeue(ctx)
    s.syncRouteStatus(ctx, report)
    return nil
}
func (s *StatusSyncer) syncRouteStatus(ctx context.Context, report Report) {
    retry.Do(func() error {
        route, err := s.client.Get(ctx, key)
        if err != nil {
            if apierrors.IsNotFound(err) { return nil }
            return err
        }
        status := report.BuildRouteStatus(ctx, route)
        route.Status = *status
        return s.client.Status().Update(ctx, route)
    })
}
        """,
        encoding="utf-8",
    )
    assert "transient-cache-notfound-drops-status" in _roots(run_static_transfer_review(tmp_path, [source.name]))


def test_one_shot_status_report_retries_notfound_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "status_syncer.go"
    source.write_text(
        """
package syncer
func (s *StatusSyncer) Start(ctx context.Context) error {
    report, _ := s.reportQueue.Dequeue(ctx)
    s.syncRouteStatus(ctx, report)
    return nil
}
func (s *StatusSyncer) syncRouteStatus(ctx context.Context, report Report) {
    retry.Do(func() error {
        route, err := s.client.Get(ctx, key)
        if err != nil {
            if apierrors.IsNotFound(err) { return err }
            return err
        }
        status := report.BuildRouteStatus(ctx, route)
        route.Status = *status
        return s.client.Status().Update(ctx, route)
    })
}
        """,
        encoding="utf-8",
    )
    assert "transient-cache-notfound-drops-status" not in _roots(run_static_transfer_review(tmp_path, [source.name]))


def test_scoped_user_api_key_missing_from_permission_gate_is_reported(tmp_path: Path) -> None:
    handler = tmp_path / "handler.go"
    auth = tmp_path / "service_apikeys_api.go"
    handler.write_text(
        """
package api
func (h *Handler) requirePermission(ctx context.Context, req *Request, action, resource string) error {
    apiKey := extractAPIKey(req)
    if h.checkAdminAPIKey(apiKey) { return nil }
    token := h.extractBearerToken(req)
    if token == "" { return NewClientError(401, "no authorization token provided") }
    session, err := h.auth.ValidateSession(ctx, token)
    if err != nil { return err }
    return h.auth.HasPermissionAPI(ctx, session.UserID, action, resource)
}
        """,
        encoding="utf-8",
    )
    auth.write_text(
        """
package auth
type CreateAPIKeyRequest struct { Permissions []Permission }
func (s *Service) CreateAPIKeyAPI(ctx context.Context, req CreateAPIKeyRequest) error {
    return s.CreateAPIKey(ctx, req.Permissions)
}
func (s *Service) ValidateUserAPIKeyAPI(ctx context.Context, apiKey string) error {
    return s.ValidateUserAPIKey(ctx, apiKey)
}
        """,
        encoding="utf-8",
    )
    assert "credential-scope-not-enforced" in _roots(
        run_static_transfer_review(tmp_path, [handler.name, auth.name])
    )


def test_scoped_user_api_key_checked_before_bearer_fallback_is_clean(tmp_path: Path) -> None:
    handler = tmp_path / "handler.go"
    auth = tmp_path / "service_apikeys_api.go"
    handler.write_text(
        """
package api
func (h *Handler) requirePermission(ctx context.Context, req *Request, action, resource string) error {
    apiKey := extractAPIKey(req)
    if h.checkAdminAPIKey(apiKey) { return nil }
    if apiKey != "" {
        return h.auth.HasAPIKeyPermissionAPI(ctx, apiKey, action, resource)
    }
    token := h.extractBearerToken(req)
    if token == "" { return NewClientError(401, "no authorization token provided") }
    return nil
}
        """,
        encoding="utf-8",
    )
    auth.write_text(
        """
package auth
type CreateAPIKeyRequest struct { Permissions []Permission }
func (s *Service) CreateAPIKeyAPI(ctx context.Context, req CreateAPIKeyRequest) error {
    return s.CreateAPIKey(ctx, req.Permissions)
}
func (s *Service) ValidateUserAPIKeyAPI(ctx context.Context, apiKey string) error {
    return s.ValidateUserAPIKey(ctx, apiKey)
}
        """,
        encoding="utf-8",
    )
    assert "credential-scope-not-enforced" not in _roots(
        run_static_transfer_review(tmp_path, [handler.name, auth.name])
    )


def test_authoritative_sqlite_rebuild_in_place_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "knowledge_index.py"
    source.write_text(
        """
import sqlite3

def _initialize_database(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    return sqlite3.connect(db_path)

def rebuild_knowledge_index(layout):
    with _initialize_database(layout.knowledge_db) as conn:
        conn.execute("insert into pages values (?)", ("page",))
        conn.commit()
        """,
        encoding="utf-8",
    )
    assert "destructive-in-place-rebuild" in _roots(run_static_transfer_review(tmp_path, [source.name]))


def test_temporary_sqlite_rebuild_with_atomic_replace_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "knowledge_index.py"
    source.write_text(
        """
import os, sqlite3

def rebuild_knowledge_index(layout):
    temp_path = layout.knowledge_db.with_suffix(".tmp")
    if temp_path.exists():
        temp_path.unlink()
    with sqlite3.connect(temp_path) as conn:
        conn.execute("insert into pages values (?)", ("page",))
        conn.commit()
    os.replace(temp_path, layout.knowledge_db)
        """,
        encoding="utf-8",
    )
    assert "destructive-in-place-rebuild" not in _roots(run_static_transfer_review(tmp_path, [source.name]))
