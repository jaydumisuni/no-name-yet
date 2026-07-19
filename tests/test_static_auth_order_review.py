from __future__ import annotations

from pathlib import Path

from main_review.static_auth_order_review import run_static_auth_order_review


ROOT = "protected-refetch-before-auth-session-ready"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_mfa_cache_invalidation_before_verify_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Settings.tsx"
    source.write_text(
        """
function MfaCard() {
  const qc = useQueryClient();
  const finishEnable = () => {
    mfaVerify(code).then(() => setCode(''));
  };
  const enable = useMutation({
    mutationFn: () => mfaEnable(code, scope),
    onSuccess: () => {
      setSetup(null);
      qc.invalidateQueries();
      finishEnable();
    },
  });
  return null;
}
        """,
        encoding="utf-8",
    )
    result = run_static_auth_order_review(tmp_path, ["Settings.tsx"])
    assert ROOT in _roots(result)


def test_verify_inside_mutation_before_onsettled_invalidation_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Settings.tsx"
    source.write_text(
        """
function MfaCard() {
  const qc = useQueryClient();
  const enable = useMutation({
    mutationFn: async () => {
      await mfaEnable(code, scope);
      await mfaVerify(code);
    },
    onSuccess: () => setSetup(null),
    onSettled: () => qc.invalidateQueries(),
  });
  return null;
}
        """,
        encoding="utf-8",
    )
    result = run_static_auth_order_review(tmp_path, ["Settings.tsx"])
    assert ROOT not in _roots(result)


def test_disabling_auth_then_invalidating_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Settings.tsx"
    source.write_text(
        """
function MfaCard() {
  const qc = useQueryClient();
  const disable = useMutation({
    mutationFn: () => mfaDisable(code),
    onSuccess: () => qc.invalidateQueries(),
  });
  return null;
}
        """,
        encoding="utf-8",
    )
    result = run_static_auth_order_review(tmp_path, ["Settings.tsx"])
    assert ROOT not in _roots(result)
