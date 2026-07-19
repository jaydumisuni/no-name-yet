from __future__ import annotations

from pathlib import Path

from main_review.static_url_path_contract_review import run_static_url_path_contract_review


ROOT = "caller-controlled-path-segment-not-percent-escaped"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_command_id_concatenated_into_request_path_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "project.go"
    source.write_text(
        '''
package main

func projectSet(c *apiClient, rest []string) error {
    id, err := projectSingleID("project set", "example", rest)
    if err != nil { return err }
    _, err = c.patch(context.Background(), "/api/projects/"+id, map[string]any{"status":"done"})
    return err
}
        ''',
        encoding="utf-8",
    )

    result = run_static_url_path_contract_review(tmp_path, ["project.go"])

    assert ROOT in _roots(result)


def test_percent_escaped_path_segment_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "project.go"
    source.write_text(
        '''
package main

import "net/url"

func projectSet(c *apiClient, rest []string) error {
    id, err := projectSingleID("project set", "example", rest)
    if err != nil { return err }
    escapedID := url.PathEscape(id)
    _, err = c.patch(context.Background(), "/api/projects/"+escapedID, map[string]any{"status":"done"})
    return err
}
        ''',
        encoding="utf-8",
    )

    result = run_static_url_path_contract_review(tmp_path, ["project.go"])

    assert ROOT not in _roots(result)


def test_constant_path_suffix_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "health.go"
    source.write_text(
        '''
package main

func health(c *apiClient) error {
    suffix := "status"
    _, err := c.get(context.Background(), "/api/health/"+suffix)
    return err
}
        ''',
        encoding="utf-8",
    )

    result = run_static_url_path_contract_review(tmp_path, ["health.go"])

    assert ROOT not in _roots(result)
