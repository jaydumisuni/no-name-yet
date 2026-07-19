from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_9_review import run_static_transfer_9_review


PATH_ROOT = "untrusted-relative-path-can-escape-mounted-root"
INTERPRETER_ROOT = "untrusted-data-interpolated-into-interpreter-source"
HTTP_ROOT = "http-response-body-read-without-close"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_guest_relative_path_combined_without_containment_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Kernel.cs"
    source.write_text(
        r'''
class Kernel {
  static string ResolveGuestPath(string guestPath) {
    var app0Root = GetApp0Root();
    var relative = guestPath.Replace('/', Path.DirectorySeparatorChar);
    return Path.Combine(app0Root, relative);
  }
  private static string NormalizeMountRelativePath(string relativePath) {
    return relativePath.TrimStart('/', '\\').Replace('/', Path.DirectorySeparatorChar);
  }
}
''',
        encoding="utf-8",
    )
    assert PATH_ROOT in _roots(run_static_transfer_9_review(tmp_path, ["Kernel.cs"]))


def test_dot_segment_clamp_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Kernel.cs"
    source.write_text(
        r'''
class Kernel {
  static string ResolveGuestPath(string guestPath) {
    var app0Root = GetApp0Root();
    var relative = NormalizeMountRelativePath(guestPath);
    return Path.Combine(app0Root, relative);
  }
  private static string NormalizeMountRelativePath(string relativePath) {
    var resolved = new List<string>();
    foreach (var segment in relativePath.Split('/', '\\')) {
      if (segment == "..") {
        if (resolved.Count > 0) resolved.RemoveAt(resolved.Count - 1);
        continue;
      }
      resolved.Add(segment);
    }
    return string.Join(Path.DirectorySeparatorChar, resolved);
  }
}
''',
        encoding="utf-8",
    )
    assert PATH_ROOT not in _roots(run_static_transfer_9_review(tmp_path, ["Kernel.cs"]))


def test_canonical_candidate_with_root_guard_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Upload.cs"
    source.write_text(
        r'''
class Upload {
  static string ResolveUploadPath(string requestPath) {
    var uploadRoot = GetUploadRoot();
    var candidate = Path.GetFullPath(Path.Combine(uploadRoot, requestPath));
    var prefix = Path.TrimEndingDirectorySeparator(uploadRoot) + Path.DirectorySeparatorChar;
    if (!candidate.StartsWith(prefix) && !string.Equals(candidate, uploadRoot)) throw new Exception();
    return candidate;
  }
}
''',
        encoding="utf-8",
    )
    assert PATH_ROOT not in _roots(run_static_transfer_9_review(tmp_path, ["Upload.cs"]))


def test_formatted_user_data_in_python_source_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "search.rs"
    source.write_text(
        r'''
let output = python_run_with_env(
    &["-c", &format!(
        "from ai.store import search; print(search({:?}, path={:?}))",
        params.query,
        params.path,
    )],
    &python_env(config),
)?;
''',
        encoding="utf-8",
    )
    assert INTERPRETER_ROOT in _roots(run_static_transfer_9_review(tmp_path, ["search.rs"]))


def test_fixed_module_with_json_arguments_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "search.rs"
    source.write_text(
        r'''
let args = serde_json::json!({"query": params.query, "path": params.path});
let output = python_run_with_env(
    &["-m", "ai.bridge"],
    &bridge_env(config, &args),
)?;
''',
        encoding="utf-8",
    )
    assert INTERPRETER_ROOT not in _roots(run_static_transfer_9_review(tmp_path, ["search.rs"]))


def test_http_response_body_read_without_close_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "client.go"
    source.write_text(
        r'''
package client
func (client *Client) RequestJSON(ctx context.Context, output any) error {
    response, err := request(ctx, client.http)
    if err != nil { return err }
    bodyBytes, err := io.ReadAll(response.Body)
    if err != nil { return err }
    return json.Unmarshal(bodyBytes, output)
}
''',
        encoding="utf-8",
    )
    assert HTTP_ROOT in _roots(run_static_transfer_9_review(tmp_path, ["client.go"]))


def test_http_response_body_deferred_close_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "client.go"
    source.write_text(
        r'''
package client
func (client *Client) RequestJSON(ctx context.Context, output any) error {
    response, err := request(ctx, client.http)
    if err != nil { return err }
    defer response.Body.Close()
    bodyBytes, err := io.ReadAll(response.Body)
    if err != nil { return err }
    return json.Unmarshal(bodyBytes, output)
}
''',
        encoding="utf-8",
    )
    assert HTTP_ROOT not in _roots(run_static_transfer_9_review(tmp_path, ["client.go"]))


def test_untouched_response_returned_to_caller_is_out_of_scope(tmp_path: Path) -> None:
    source = tmp_path / "client.go"
    source.write_text(
        r'''
package client
func (client *Client) Open(ctx context.Context) (*http.Response, error) {
    response, err := request(ctx, client.http)
    if err != nil { return nil, err }
    return response, nil
}
''',
        encoding="utf-8",
    )
    assert HTTP_ROOT not in _roots(run_static_transfer_9_review(tmp_path, ["client.go"]))
