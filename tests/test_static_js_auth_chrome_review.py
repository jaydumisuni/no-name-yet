from __future__ import annotations

from pathlib import Path

from main_review.static_js_auth_chrome_review import run_static_js_auth_chrome_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_session_mutation_without_mounted_topbar_channel_is_reported(tmp_path: Path) -> None:
    (tmp_path / "session.js").write_text(
        """
let _currentUser = null;
window.AppSession = {
  get user() { return _currentUser; },
  setUser(user) {
    _currentUser = user;
  },
  clearSession() {
    _currentUser = null;
  },
};
        """,
        encoding="utf-8",
    )
    (tmp_path / "topbar.js").write_text(
        """
function renderTopbar() {
  return `<button data-action="open-auth">sign in</button>`;
}

export function mountTopbar(root, shellRoot) {
  root.innerHTML = renderTopbar();
  const signIn = root.querySelector('[data-action="open-auth"]');
  signIn.addEventListener('click', openAuth);
  window.addEventListener('kt:pushstate', closeDrawer);
  return () => {
    window.removeEventListener('kt:pushstate', closeDrawer);
  };
}
        """,
        encoding="utf-8",
    )

    result = run_static_js_auth_chrome_review(
        tmp_path,
        ["session.js", "topbar.js"],
    )

    assert "auth-session-change-not-invalidating-mounted-chrome" in _roots(result)


def test_matching_auth_event_connects_session_and_topbar(tmp_path: Path) -> None:
    (tmp_path / "session.js").write_text(
        """
let _currentUser = null;
window.AppSession = {
  setUser(user) {
    _currentUser = user;
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
  },
  clearSession() {
    _currentUser = null;
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user: null } }));
  },
};
        """,
        encoding="utf-8",
    )
    (tmp_path / "topbar.js").write_text(
        """
function renderTopbar(user) {
  return user
    ? `<a class="profile" href="/account">${user.email}</a>`
    : `<button data-action="open-auth">sign in</button>`;
}

export function mountTopbar(root, shellRoot) {
  const updateAuthArea = (event) => {
    root.innerHTML = renderTopbar(event.detail.user);
  };
  root.innerHTML = renderTopbar(null);
  window.addEventListener('auth:changed', updateAuthArea);
  return () => window.removeEventListener('auth:changed', updateAuthArea);
}
        """,
        encoding="utf-8",
    )

    result = run_static_js_auth_chrome_review(
        tmp_path,
        ["session.js", "topbar.js"],
    )

    assert "auth-session-change-not-invalidating-mounted-chrome" not in _roots(result)


def test_mismatched_event_names_do_not_form_a_channel(tmp_path: Path) -> None:
    (tmp_path / "session.js").write_text(
        """
let currentUser = null;
const session = {
  setUser(user) {
    currentUser = user;
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { user } }));
  },
};
        """,
        encoding="utf-8",
    )
    (tmp_path / "header.js").write_text(
        """
export function mountHeader(root) {
  root.innerHTML = '<button class="signin">log in</button>';
  window.addEventListener('session:updated', refreshHeader);
}
        """,
        encoding="utf-8",
    )

    result = run_static_js_auth_chrome_review(
        tmp_path,
        ["session.js", "header.js"],
    )

    assert "auth-session-change-not-invalidating-mounted-chrome" in _roots(result)


def test_auth_surface_without_session_mutator_is_clean(tmp_path: Path) -> None:
    (tmp_path / "topbar.js").write_text(
        """
export function mountTopbar(root) {
  root.innerHTML = '<button data-action="open-auth">sign in</button>';
  root.querySelector('[data-action="open-auth"]').addEventListener('click', openAuth);
}
        """,
        encoding="utf-8",
    )

    result = run_static_js_auth_chrome_review(tmp_path, ["topbar.js"])

    assert "auth-session-change-not-invalidating-mounted-chrome" not in _roots(result)


def test_native_auth_subscription_is_clean(tmp_path: Path) -> None:
    (tmp_path / "session.js").write_text(
        """
let currentUser = null;
const session = {
  setUser(user) {
    currentUser = user;
  },
};
        """,
        encoding="utf-8",
    )
    (tmp_path / "chrome.js").write_text(
        """
export function mountChrome(root) {
  root.innerHTML = '<button class="signin">sign in</button>';
  const unsubscribe = onAuthStateChanged(auth, (user) => {
    root.innerHTML = user ? '<a class="profile">account</a>' : '<button>sign in</button>';
  });
  return unsubscribe;
}
        """,
        encoding="utf-8",
    )

    result = run_static_js_auth_chrome_review(
        tmp_path,
        ["session.js", "chrome.js"],
    )

    assert "auth-session-change-not-invalidating-mounted-chrome" not in _roots(result)
