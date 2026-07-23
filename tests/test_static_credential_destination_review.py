from __future__ import annotations

from pathlib import Path

from main_review.static_credential_destination_review import (
    run_static_credential_destination_review,
)


ROOT_CAUSE = "credential-attached-without-exact-destination-binding"


def _review(tmp_path: Path, name: str, source: str) -> dict:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return run_static_credential_destination_review(tmp_path, [name])


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_real_lumi_prefixed_snapshot_is_reported(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "browser-extension/security-shim.js",
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
    assert ROOT_CAUSE in _roots(result)
    finding = result["findings"][0]
    assert finding["officer"] == "Medic"
    assert finding["capability"] == "security_taint"


def test_real_lumi_exact_configured_origin_repair_is_clean(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "browser-extension/security-shim.js",
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
    assert ROOT_CAUSE not in _roots(result)


def test_typescript_transfer_host_category_and_path_prefix_is_reported(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "src/authenticated-client.ts",
        r'''
        export async function request(target: string, sessionToken: string) {
          const endpoint = new URL(target);
          const allowedHosts = /^(localhost|127\.0\.0\.1)$/;
          const headers: Record<string, string> = {};
          if (allowedHosts.test(endpoint.hostname) && endpoint.pathname.indexOf("/rpc/") === 0) {
            headers.Authorization = `Bearer ${sessionToken}`;
          }
          return fetch(endpoint, { headers });
        }
        ''',
    )
    assert ROOT_CAUSE in _roots(result)


def test_python_unrelated_language_transfer_is_reported(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "client/auth.py",
        r'''
        from urllib.parse import urlparse

        TRUSTED_HOSTS = {"localhost", "127.0.0.1"}

        def request(target: str, token: str):
            parsed = urlparse(target)
            headers = {}
            if parsed.hostname in TRUSTED_HOSTS and parsed.path.startswith("/api/"):
                headers["Authorization"] = f"Bearer {token}"
            return send(target, headers=headers)
        ''',
    )
    assert ROOT_CAUSE in _roots(result)


def test_python_exact_scheme_and_netloc_binding_is_clean(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "client/auth.py",
        r'''
        from urllib.parse import urlparse

        def request(target: str, configured_server: str, token: str):
            parsed = urlparse(target)
            configured = urlparse(configured_server)
            if (parsed.scheme, parsed.netloc) != (configured.scheme, configured.netloc):
                return send(target)
            if not parsed.path.startswith("/api/"):
                return send(target)
            headers = {"Authorization": f"Bearer {token}"}
            return send(target, headers=headers)
        ''',
    )
    assert ROOT_CAUSE not in _roots(result)


def test_broad_destination_check_without_credential_sink_is_clean(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "src/route.ts",
        r'''
        export function isLocalApi(value: string): boolean {
          const url = new URL(value);
          return url.hostname === "localhost" && url.pathname.startsWith("/api/");
        }
        ''',
    )
    assert result["finding_count"] == 0


def test_fixed_constant_service_client_is_clean(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "src/client.ts",
        r'''
        export async function callService(token: string) {
          const headers = new Headers();
          headers.set("Authorization", `Bearer ${token}`);
          return fetch("https://api.example.com/v1/me", { headers });
        }
        ''',
    )
    assert result["finding_count"] == 0


def test_hidden_holdout_exact_origin_alias_is_clean(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "src/transport.mjs",
        r'''
        export async function send(input, cfg, credential) {
          const destination = new URL(input);
          const trusted = new URL(cfg.endpoint);
          if (destination.origin !== trusted.origin) return fetch(input);
          if (!destination.pathname.includes("/service/")) return fetch(input);
          const options = { headers: { Authorization: `Bearer ${credential}` } };
          return fetch(input, options);
        }
        ''',
    )
    assert result["finding_count"] == 0


def test_hidden_holdout_broad_subdomain_allowlist_is_reported(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        "src/transport.mjs",
        r'''
        export async function send(input, credential) {
          const destination = new URL(input);
          const headers = {};
          if (destination.hostname.endsWith(".internal") && destination.pathname.includes("/service/")) {
            headers["Authorization"] = `Bearer ${credential}`;
          }
          return fetch(input, { headers });
        }
        ''',
    )
    assert ROOT_CAUSE in _roots(result)
