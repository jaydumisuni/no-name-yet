from __future__ import annotations

from pathlib import Path

from main_review.static_cross_path_review import run_static_cross_path_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_config_validator_using_permissive_unmarshal_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "validate.go"
    source.write_text(
        """
package config
func ValidateBytes(data []byte) (FileConfig, []Issue) {
    var cfg FileConfig
    if err := json.Unmarshal(data, &cfg); err != nil { return FileConfig{}, []Issue{{Message: err.Error()}} }
    return cfg, validateSemantics(cfg)
}
        """,
        encoding="utf-8",
    )
    assert "permissive-config-validation" in _roots(run_static_cross_path_review(tmp_path, ["validate.go"]))


def test_config_validator_with_unknown_field_scan_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "validate.go"
    source.write_text(
        """
package config
func ValidateBytes(data []byte) (FileConfig, []Issue) {
    var cfg FileConfig
    if err := json.Unmarshal(data, &cfg); err != nil { return FileConfig{}, []Issue{{Message: err.Error()}} }
    issues := validateSemantics(cfg)
    issues = append(issues, unknownFieldIssues(data)...)
    return cfg, issues
}
        """,
        encoding="utf-8",
    )
    assert "permissive-config-validation" not in _roots(run_static_cross_path_review(tmp_path, ["validate.go"]))


def test_multiple_controllers_replacing_same_status_are_reported(tmp_path: Path) -> None:
    first = tmp_path / "first_controller.go"
    second = tmp_path / "second_controller.go"
    first.write_text(
        """
package controller
func (r *FirstReconciler) Reconcile(ctx context.Context) error {
    instance := &v1alpha1.Tenant{}
    instance.Status.StorageClasses = classes
    return r.Status().Update(ctx, instance)
}
        """,
        encoding="utf-8",
    )
    second.write_text(
        """
package controller
func (r *SecondReconciler) Reconcile(ctx context.Context) error {
    instance := &v1alpha1.Tenant{}
    instance.Status.Phase = Ready
    return r.Status().Update(ctx, instance)
}
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(tmp_path, [first.name, second.name])
    assert "shared-status-full-replacement" in _roots(result)


def test_shared_status_writers_using_merge_patch_are_clean(tmp_path: Path) -> None:
    first = tmp_path / "first_controller.go"
    second = tmp_path / "second_controller.go"
    first.write_text(
        """
package controller
func (r *FirstReconciler) patch(ctx context.Context) error {
    latest := &v1alpha1.Tenant{}
    base := latest.DeepCopy()
    latest.Status.StorageClasses = classes
    return r.Status().Patch(ctx, latest, client.MergeFrom(base))
}
        """,
        encoding="utf-8",
    )
    second.write_text(
        """
package controller
func (r *SecondReconciler) patch(ctx context.Context) error {
    latest := &v1alpha1.Tenant{}
    base := latest.DeepCopy()
    latest.Status.Phase = Ready
    return r.Status().Patch(ctx, latest, client.MergeFrom(base))
}
        """,
        encoding="utf-8",
    )
    result = run_static_cross_path_review(tmp_path, [first.name, second.name])
    assert "shared-status-full-replacement" not in _roots(result)


def test_bulk_download_cached_without_retry_or_completeness_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "instrument_master.py"
    source.write_text(
        """
import json, requests

def download_instrument_master():
    response = requests.get(SCRIP_MASTER_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    CACHE_PATH.write_text(json.dumps(data), encoding="utf-8")
    return data
        """,
        encoding="utf-8",
    )
    assert "unvalidated-external-data-cache" in _roots(run_static_cross_path_review(tmp_path, [source.name]))


def test_bulk_download_with_retry_and_completeness_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "instrument_master.py"
    source.write_text(
        """
import json, requests

def download_instrument_master():
    for attempt in range(4):
        response = requests.get(SCRIP_MASTER_URL, timeout=60)
        data = response.json()
        if not isinstance(data, list) or len(data) < 10000:
            continue
        CACHE_PATH.write_text(json.dumps(data), encoding="utf-8")
        return data
    raise RuntimeError("incomplete catalog")
        """,
        encoding="utf-8",
    )
    assert "unvalidated-external-data-cache" not in _roots(run_static_cross_path_review(tmp_path, [source.name]))
