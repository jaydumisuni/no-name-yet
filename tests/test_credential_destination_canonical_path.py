from __future__ import annotations

from pathlib import Path

from main_review.external_static_review import run_external_static_review


ROOT_CAUSE = "credential-attached-without-exact-destination-binding"


def _write(tmp_path: Path, source: str) -> str:
    relative = "browser-extension/security-shim.js"
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return relative


def _admitted_roots(result: dict) -> set[str]:
    council = result.get("officer_council", {})
    return {
        str(item.get("root_cause"))
        for item in council.get("admitted_findings", [])
        if isinstance(item, dict)
    }


def test_canonical_external_review_admits_real_lumi_origin_boundary(tmp_path: Path) -> None:
    relative = _write(
        tmp_path,
        r'''
        const nativeFetch = globalThis.fetch.bind(globalThis);
        const loopbackHosts = new Set(["localhost", "127.0.0.1", "::1"]);
        function isApiRequest(value) {
          const url = new URL(typeof value === "string" ? value : value.url);
          return loopbackHosts.has(url.hostname) && url.pathname.startsWith("/api/");
        }
        globalThis.fetch = async function authenticatedFetch(input, init = {}) {
          if (!isApiRequest(input)) return nativeFetch(input, init);
          const token = await storedToken();
          const headers = new Headers(init.headers);
          if (token && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${token}`);
          }
          return nativeFetch(input, { ...init, headers });
        };
        ''',
    )
    result = run_external_static_review(tmp_path, [relative], review_mode="snapshot")
    assert ROOT_CAUSE in _admitted_roots(result)
    assert result["verdict"]["verdict"] in {"REQUEST_CHANGES", "BLOCK"}


def test_canonical_external_review_keeps_exact_origin_repair_clean(tmp_path: Path) -> None:
    relative = _write(
        tmp_path,
        r'''
        async function securitySettings() {
          const values = await chrome.storage.local.get({ apiToken: "", server: "http://localhost:7000" });
          return { token: values.apiToken, serverOrigin: new URL(values.server).origin };
        }
        globalThis.fetch = async function authenticatedFetch(input, init = {}) {
          const url = new URL(typeof input === "string" ? input : input.url);
          if (!url.pathname.startsWith("/api/")) return nativeFetch(input, init);
          const settings = await securitySettings();
          if (!settings.serverOrigin || url.origin !== settings.serverOrigin) return nativeFetch(input, init);
          const headers = new Headers(init.headers);
          if (settings.token && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${settings.token}`);
          }
          return nativeFetch(input, { ...init, headers });
        };
        ''',
    )
    result = run_external_static_review(tmp_path, [relative], review_mode="snapshot")
    assert ROOT_CAUSE not in _admitted_roots(result)
