from __future__ import annotations

from pathlib import Path

from main_review.static_roundtrip_review import run_static_roundtrip_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_subset_type_get_modify_put_roundtrip_is_reported(tmp_path: Path) -> None:
    api = tmp_path / "api"
    config = tmp_path / "config"
    api.mkdir()
    config.mkdir()
    (config / "types.go").write_text(
        """
package config
type Configuration struct {
    Version int `json:"version"`
    Folders []Folder `json:"folders"`
}
type Folder struct { ID string `json:"id"` }
        """,
        encoding="utf-8",
    )
    (api / "connection.go").write_text(
        """
package api
func (c *Client) fetchConfig() (*config.Configuration, error) {
    responseBody := &config.Configuration{}
    data, err := c.jsonRequest(ConfigEndpoint, "GET", nil)
    if err != nil { return nil, err }
    if err := json.Unmarshal(data, responseBody); err != nil { return nil, err }
    return responseBody, nil
}
func (c *Client) PublishConfig(conf config.Configuration) error {
    _, err := c.jsonRequest(ConfigEndpoint, "PUT", conf)
    return err
}
        """,
        encoding="utf-8",
    )
    result = run_static_roundtrip_review(
        tmp_path,
        ["api/connection.go", "config/types.go"],
    )
    assert "lossy-typed-json-roundtrip" in _roots(result)


def test_raw_unknown_field_preservation_is_clean(tmp_path: Path) -> None:
    api = tmp_path / "api"
    config = tmp_path / "config"
    api.mkdir()
    config.mkdir()
    (config / "types.go").write_text(
        """
package config
type Configuration struct {
    Version int `json:"version"`
    Extras map[string]json.RawMessage `json:"-"`
}
func (c *Configuration) UnmarshalJSON(data []byte) error { return preserveUnknown(data, c) }
func (c Configuration) MarshalJSON() ([]byte, error) { return mergeUnknown(c.Extras, c) }
        """,
        encoding="utf-8",
    )
    (api / "connection.go").write_text(
        """
package api
func (c *Client) fetchConfig() (*config.Configuration, error) {
    responseBody := &config.Configuration{}
    data, err := c.jsonRequest(ConfigEndpoint, "GET", nil)
    if err != nil { return nil, err }
    if err := json.Unmarshal(data, responseBody); err != nil { return nil, err }
    return responseBody, nil
}
func (c *Client) PublishConfig(conf config.Configuration) error {
    _, err := c.jsonRequest(ConfigEndpoint, "PUT", conf)
    return err
}
        """,
        encoding="utf-8",
    )
    result = run_static_roundtrip_review(
        tmp_path,
        ["api/connection.go", "config/types.go"],
    )
    assert "lossy-typed-json-roundtrip" not in _roots(result)


def test_read_only_typed_decode_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "reader.go"
    source.write_text(
        """
package reader
type Configuration struct { Version int `json:"version"` }
func fetchConfig(data []byte) (*Configuration, error) {
    responseBody := &Configuration{}
    if err := json.Unmarshal(data, responseBody); err != nil { return nil, err }
    return responseBody, nil
}
        """,
        encoding="utf-8",
    )
    assert "lossy-typed-json-roundtrip" not in _roots(
        run_static_roundtrip_review(tmp_path, [source.name])
    )
