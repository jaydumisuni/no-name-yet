from __future__ import annotations

from pathlib import Path

from main_review.static_cross_path_review import run_static_cross_path_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_policy_callback_replacing_validated_permissions_requires_post_validation(tmp_path: Path) -> None:
    source = tmp_path / "server.go"
    source.write_text(
        """
package server
func authenticate() {
    if perms.CriticalOptions[sourceAddressOption] != "" {
        checkSourceAddress(remote, perms.CriticalOptions[sourceAddressOption])
    }
    perms, authErr = config.VerifiedPolicyCallback(session, perms)
    if authErr == nil { accept() }
}
        """,
        encoding="utf-8",
    )
    assert "post-validation-policy-mutation" in _roots(run_static_cross_path_review(tmp_path, ["server.go"]))


def test_policy_callback_post_validation_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "server.go"
    source.write_text(
        """
package server
func authenticate() {
    if perms.CriticalOptions[sourceAddressOption] != "" {
        checkSourceAddress(remote, perms.CriticalOptions[sourceAddressOption])
    }
    perms, authErr = config.VerifiedPolicyCallback(session, perms)
    if authErr == nil && perms.CriticalOptions[sourceAddressOption] != "" {
        authErr = checkSourceAddress(remote, perms.CriticalOptions[sourceAddressOption])
    }
}
        """,
        encoding="utf-8",
    )
    assert "post-validation-policy-mutation" not in _roots(run_static_cross_path_review(tmp_path, ["server.go"]))


def test_transport_without_pre_dispatch_authorization_is_reported(tmp_path: Path) -> None:
    core = tmp_path / "core.go"
    server = tmp_path / "server.go"
    core.write_text(
        """
package core
func (c *Core) CallTool() error {
    allowed, err := c.admission.AllowToolCall(ctx, identity, tool, args)
    if err != nil || !allowed { return ErrAuthorizationFailed }
    return dispatch()
}
        """,
        encoding="utf-8",
    )
    server.write_text(
        """
package server
// Authorization is enforced by the core after SDK routing.
func (s *Server) Handler() http.Handler {
    return NewStreamableHTTPServer(s.mcpServer)
}
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(tmp_path, ["core.go", "server.go"])
    assert "transport-authorization-representation-gap" in _roots(result)


def test_transport_with_shared_call_gate_is_clean(tmp_path: Path) -> None:
    core = tmp_path / "core.go"
    server = tmp_path / "server.go"
    core.write_text(
        """
package core
func (c *Core) CallTool() error {
    allowed, err := c.admission.AllowToolCall(ctx, identity, tool, args)
    if err != nil || !allowed { return ErrAuthorizationFailed }
    return dispatch()
}
func (c *Core) CheckToolCall() error { return c.authorizeToolCall() }
        """,
        encoding="utf-8",
    )
    server.write_text(
        """
package server
func (s *Server) Handler() http.Handler {
    return NewStreamableHTTPServer(s.mcpServer, WithCallGate(s.authzCallGate()))
}
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(tmp_path, ["core.go", "server.go"])
    assert "transport-authorization-representation-gap" not in _roots(result)


def test_legacy_permissions_missing_active_backend_are_reported(tmp_path: Path) -> None:
    directory = tmp_path / "permissions"
    directory.mkdir()
    (directory / "role_v2_access.py").write_text(
        """
class RoleV2KesselAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return WorkspaceInventoryAccessChecker().check_resource_access(request)
        """,
        encoding="utf-8",
    )
    (directory / "principal_access.py").write_text(
        """
class PrincipalAccessPermission(BasePermission):
    def has_permission(self, request, view):
        if request.user.access.get("principal", {}).get("read", []):
            return True
        return False
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(
        tmp_path,
        ["permissions/role_v2_access.py", "permissions/principal_access.py"],
    )
    assert "authorization-backend-parity-gap" in _roots(result)


def test_legacy_permissions_using_shared_backend_fallback_are_clean(tmp_path: Path) -> None:
    directory = tmp_path / "permissions"
    directory.mkdir()
    (directory / "role_v2_access.py").write_text(
        """
class RoleV2KesselAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return WorkspaceInventoryAccessChecker().check_resource_access(request)
        """,
        encoding="utf-8",
    )
    (directory / "principal_access.py").write_text(
        """
class PrincipalAccessPermission(BasePermission):
    def has_permission(self, request, view):
        if request.user.access.get("principal", {}).get("read", []):
            return True
        return check_v2_kessel_access(request)
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(
        tmp_path,
        ["permissions/role_v2_access.py", "permissions/principal_access.py"],
    )
    assert "authorization-backend-parity-gap" not in _roots(result)
