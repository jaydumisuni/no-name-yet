from __future__ import annotations

from pathlib import Path

import pytest

from main_review.battle_compare import _write_patch_workspace
from main_review.boundary import assert_safe_path, check_action_boundary
from main_review.github_diff_fetch import PullRequestFile
from main_review.production_hardening import (
    HardeningError,
    assess_token_scopes,
    enforce_mission_permissions,
    normalize_changed_files,
    normalize_repository_path,
    normalize_time_budget,
    redact_secrets,
    validate_github_base_url,
    validate_repository_slug,
)
from main_review.review_contract import normalize_review_request


def test_boundary_denies_unknown_and_dangerous_context_before_allowlist() -> None:
    assert check_action_boundary("scan")["allowed"] is True
    assert check_action_boundary("invented-action")["allowed"] is False
    assert check_action_boundary("scan", {"requires_write_token": True})["allowed"] is False
    assert check_action_boundary("review", {"executes_untrusted_code": True})["allowed"] is False
    assert check_action_boundary("collect_comments", {"requires_shell": True})["allowed"] is False
    assert check_action_boundary("ingest_external_evidence", {"exports_private_data": True})["allowed"] is False


def test_repository_path_sandbox_rejects_traversal_absolute_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    assert normalize_repository_path(root, "src/app.py") == "src/app.py"
    for value in ["../outside/secret.txt", str(outside / "secret.txt"), "escape/secret.txt", "\x00bad"]:
        with pytest.raises(HardeningError):
            normalize_repository_path(root, value)
    assert assert_safe_path(root, "../outside/secret.txt")["allowed"] is False


def test_changed_file_normalization_deduplicates_and_bounds(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert normalize_changed_files(root, ["src/app.py", "src/app.py", "tests/test_app.py"]) == ["src/app.py", "tests/test_app.py"]
    with pytest.raises(HardeningError, match="safety limit"):
        normalize_changed_files(root, [f"src/{index}.py" for index in range(4)], limit=3)


def test_public_mission_permissions_cannot_be_escalated(monkeypatch: pytest.MonkeyPatch) -> None:
    safe = enforce_mission_permissions("default", {"read_only": True, "allow_network": True})
    assert safe == {
        "read_only": True,
        "allow_network": True,
        "allow_shell": False,
        "allow_write": False,
        "allow_untrusted_code": False,
    }
    for permissions in [
        {"allow_shell": True},
        {"allow_write": True},
        {"allow_untrusted_code": True},
        {"read_only": False},
        {"unknown": True},
    ]:
        with pytest.raises(HardeningError):
            enforce_mission_permissions("default", permissions)

    with pytest.raises(HardeningError, match="requires SERGEANT_ALLOW_ELEVATED_MISSIONS"):
        enforce_mission_permissions("internal-owner", {"allow_network": True})
    monkeypatch.setenv("SERGEANT_ALLOW_ELEVATED_MISSIONS", "true")
    elevated = enforce_mission_permissions("internal-owner", {"allow_network": True, "allow_shell": True})
    assert elevated["read_only"] is True
    assert elevated["allow_shell"] is True
    with pytest.raises(HardeningError, match="never executes"):
        enforce_mission_permissions("internal-owner", {"allow_untrusted_code": True})


def test_shared_review_contract_blocks_malicious_config_and_external_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    evidence = root / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    normalized = normalize_review_request({
        "root": str(root),
        "mode": "changed_files",
        "changed_files": ["src/app.py"],
        "external_review_file": str(evidence),
        "execution_permissions": {"read_only": True, "allow_network": False},
        "time_budget": {"seconds": 60},
    })
    assert normalized["root"] == str(root.resolve())
    assert normalized["changed_files"] == ["src/app.py"]
    assert normalized["external_review_file"] == str(evidence.resolve())
    assert normalized["time_budget"] == {"seconds": 60}

    with pytest.raises(HardeningError):
        normalize_review_request({"root": str(root), "changed_files": ["../../etc/passwd"]})
    with pytest.raises(HardeningError):
        normalize_review_request({"root": str(root), "external_review_file": str(tmp_path / "outside.json")})
    with pytest.raises(HardeningError):
        normalize_review_request({"root": str(root), "execution_permissions": {"allow_write": True}})
    with pytest.raises(TypeError, match="execution_permissions"):
        normalize_review_request({"root": str(root), "execution_permissions": "allow everything"})
    with pytest.raises(TypeError, match="time_budget"):
        normalize_review_request({"root": str(root), "time_budget": "forever"})
    with pytest.raises(HardeningError):
        normalize_review_request({"root": str(root), "policy_profile": "disable-all-guards"})
    with pytest.raises(HardeningError):
        normalize_review_request({"root": str(root), "time_budget": {"seconds": 999999}})


def test_time_budget_rejects_unknown_or_unbounded_values() -> None:
    assert normalize_time_budget({"seconds": 1}) == {"seconds": 1}
    assert normalize_time_budget({"seconds": 600}) == {"seconds": 600}
    for value in [{"seconds": 0}, {"seconds": 601}, {"minutes": 2}, {"seconds": "not-a-number"}]:
        with pytest.raises(HardeningError):
            normalize_time_budget(value)


def test_github_repository_and_host_validation_blocks_spoofing_ssrf_and_ports() -> None:
    assert validate_repository_slug("owner/repo") == "owner/repo"
    for value in ["owner/repo/extra", "owner/../repo", "https://github.com/owner/repo", "owner/repo?x=1", "owner/repo.git"]:
        with pytest.raises(HardeningError):
            validate_repository_slug(value)

    assert validate_github_base_url("https://api.github.com") == "https://api.github.com"
    assert validate_github_base_url("https://github.example.com/api/v3", allowed_hosts=["github.example.com"]) == "https://github.example.com/api/v3"
    for value in [
        "http://api.github.com",
        "https://api.github.com:444",
        "https://api.github.com.evil.test",
        "https://user:pass@api.github.com",
        "https://api.github.com/repos/owner/repo",
        "https://api.github.com?redirect=https://evil.test",
    ]:
        with pytest.raises(HardeningError):
            validate_github_base_url(value)


def test_token_scope_policy_rejects_classic_write_tokens_and_redacts_secrets() -> None:
    safe = assess_token_scopes({"X-OAuth-Scopes": "read:org, read:user"}, token_supplied=True)
    assert safe["scope_evidence"] == "verified-read-only"
    for scopes in ["repo", "public_repo", "workflow", "write:packages", "admin:org"]:
        with pytest.raises(HardeningError, match="write-capable"):
            assess_token_scopes({"X-OAuth-Scopes": scopes}, token_supplied=True)
    secret = "ghp_" + ("a" * 26)
    assert secret not in redact_secrets(f"Authorization: Bearer {secret}")


def test_live_battle_patch_materialization_rejects_pr_path_escape(tmp_path: Path) -> None:
    safe = PullRequestFile(filename="src/app.py", status="modified", patch="@@ -1 +1 @@", additions=1, deletions=1)
    assert _write_patch_workspace([safe], tmp_path) == ["src/app.py"]
    assert (tmp_path / "src" / "app.py").is_file()

    malicious = PullRequestFile(filename="../../outside.txt", status="added", patch="owned", additions=1, deletions=0)
    with pytest.raises(ValueError, match="Unsafe pull-request filename"):
        _write_patch_workspace([malicious], tmp_path)
    assert not (tmp_path.parent / "outside.txt").exists()
