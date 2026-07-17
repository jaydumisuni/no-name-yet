from __future__ import annotations

from pathlib import Path

from main_review.static_status_review import run_static_status_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_shared_status_type_is_recovered_from_local_and_parameter_writers(tmp_path: Path) -> None:
    primary = tmp_path / "clusterorder_controller.go"
    secondary = tmp_path / "storage_controller.go"
    primary.write_text(
        """
package controller
func (r *ClusterOrderReconciler) Reconcile(ctx context.Context) error {
    instance := &v1alpha1.ClusterOrder{}
    if err := r.Get(ctx, key, instance); err != nil { return err }
    instance.Status.Phase = Ready
    return r.Status().Update(ctx, instance)
}
        """,
        encoding="utf-8",
    )
    secondary.write_text(
        """
package controller
func (r *StorageReconciler) updateStorage(ctx context.Context, co *v1alpha1.ClusterOrder) error {
    co.Status.ClusterStorageJobs = jobs
    return r.Status().Update(ctx, co)
}
        """,
        encoding="utf-8",
    )
    result = run_static_status_review(tmp_path, [primary.name, secondary.name])
    assert "shared-status-full-replacement" in _roots(result)
    finding = result["findings"][0]
    assert len(finding["supporting_evidence_refs"]) == 2


def test_single_status_owner_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "controller.go"
    source.write_text(
        """
package controller
func (r *OnlyReconciler) Reconcile(ctx context.Context) error {
    instance := &v1alpha1.Tenant{}
    instance.Status.Phase = Ready
    return r.Status().Update(ctx, instance)
}
        """,
        encoding="utf-8",
    )
    assert "shared-status-full-replacement" not in _roots(run_static_status_review(tmp_path, [source.name]))


def test_field_scoped_merge_patches_are_clean(tmp_path: Path) -> None:
    first = tmp_path / "first_controller.go"
    second = tmp_path / "second_controller.go"
    first.write_text(
        """
package controller
func (r *FirstReconciler) patch(ctx context.Context, instance *v1alpha1.Tenant) error {
    base := instance.DeepCopy()
    instance.Status.StorageClasses = classes
    return r.Status().Patch(ctx, instance, client.MergeFrom(base))
}
        """,
        encoding="utf-8",
    )
    second.write_text(
        """
package controller
func (r *SecondReconciler) patch(ctx context.Context, instance *v1alpha1.Tenant) error {
    base := instance.DeepCopy()
    instance.Status.Phase = Ready
    return r.Status().Patch(ctx, instance, client.MergeFrom(base))
}
        """,
        encoding="utf-8",
    )
    assert "shared-status-full-replacement" not in _roots(
        run_static_status_review(tmp_path, [first.name, second.name])
    )
