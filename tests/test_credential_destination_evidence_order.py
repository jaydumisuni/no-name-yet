from __future__ import annotations

from pathlib import Path

from main_review.static_credential_destination_review import (
    run_static_credential_destination_review,
)


ROOT_CAUSE = "credential-attached-without-exact-destination-binding"


def test_exact_origin_check_after_sink_does_not_mask_vulnerable_attachment(
    tmp_path: Path,
) -> None:
    relative = "src/client.ts"
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r'''
        export async function request(target: string, token: string, configured: string) {
          const destination = new URL(target);
          const headers: Record<string, string> = {};
          if (destination.hostname === "localhost" && destination.pathname.startsWith("/api/")) {
            headers.Authorization = `Bearer ${token}`;
          }

          const trusted = new URL(configured);
          if (destination.origin !== trusted.origin) {
            console.warn("untrusted destination");
          }
          return fetch(destination, { headers });
        }
        ''',
        encoding="utf-8",
    )

    result = run_static_credential_destination_review(tmp_path, [relative])
    roots = {str(item.get("root_cause")) for item in result["findings"]}

    assert ROOT_CAUSE in roots
