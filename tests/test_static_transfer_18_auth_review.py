from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_18_review import run_static_transfer_18_review


COOKIE_ROOT = "successful-primary-persistence-skips-required-auth-cookie-sync"
FIELD_ROOT = "persisted-auth-refresh-field-does-not-match-canonical-token-schema"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_successful_storage_return_must_not_skip_cookie_sync(tmp_path: Path) -> None:
    source = tmp_path / "api.ts"
    source.write_text(
        '''
const authPersistStorage = {
  setItem: (name: string, value: string): void => {
    if (canUseLocalStorage()) {
      window.localStorage.setItem(name, value);
      return;
    }
    if (canUseSessionStorage()) {
      window.sessionStorage.setItem(name, value);
      return;
    }
    writeAuthCookie(JSON.parse(value));
  },
};
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["api.ts"])

    assert COOKIE_ROOT in _roots(result)


def test_shared_cookie_epilogue_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "api.ts"
    source.write_text(
        '''
const authPersistStorage = {
  setItem: (name: string, value: string): void => {
    if (canUseLocalStorage()) {
      window.localStorage.setItem(name, value);
    } else if (canUseSessionStorage()) {
      window.sessionStorage.setItem(name, value);
    }
    writeAuthCookie(JSON.parse(value));
  },
};
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["api.ts"])

    assert COOKIE_ROOT not in _roots(result)


def test_early_return_without_required_secondary_sink_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "cache.ts"
    source.write_text(
        '''
const cacheStorage = {
  setItem: (name: string, value: string): void => {
    window.localStorage.setItem(name, value);
    return;
  },
};
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["cache.ts"])

    assert COOKIE_ROOT not in _roots(result)


def test_refresh_field_must_match_canonical_persisted_schema(tmp_path: Path) -> None:
    api = tmp_path / "api.ts"
    api.write_text(
        '''
type PersistedAuthState = { state?: { refreshToken?: string | null } };
''',
        encoding="utf-8",
    )
    profile = tmp_path / "profile.tsx"
    profile.write_text(
        '''
async function deleteAccount() {
  const parsed = JSON.parse(localStorage.getItem("auth") || "{}") as {
    state?: { refresh?: string };
  };
  await authAPI.deleteAccount(parsed.state?.refresh ?? "");
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["api.ts", "profile.tsx"])

    assert FIELD_ROOT in _roots(result)


def test_canonical_refresh_token_reader_is_clean(tmp_path: Path) -> None:
    api = tmp_path / "api.ts"
    api.write_text(
        '''
type PersistedAuthState = { state?: { refreshToken?: string | null } };
''',
        encoding="utf-8",
    )
    profile = tmp_path / "profile.tsx"
    profile.write_text(
        '''
async function deleteAccount() {
  const parsed = JSON.parse(localStorage.getItem("auth") || "{}") as {
    state?: { refreshToken?: string };
  };
  await authAPI.deleteAccount(parsed.state?.refreshToken ?? "");
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["api.ts", "profile.tsx"])

    assert FIELD_ROOT not in _roots(result)
