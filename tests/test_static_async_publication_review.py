from __future__ import annotations

from pathlib import Path

from main_review.static_async_publication_review import run_static_async_publication_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_dart_provider_ref_after_await_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "controller.dart"
    source.write_text(
        """
@riverpod
class CategoryController extends _$CategoryController {
  Future<List?> build() async {
    final db = ref.watch(databaseProvider);
    final result = await fetchWithFallback(db);
    final sync = ref.read(syncProvider);
    return result;
  }
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["controller.dart"])
    assert "disposed-provider-ref-after-await" in _roots(result)


def test_dart_provider_dependency_captured_before_await_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "controller.dart"
    source.write_text(
        """
@riverpod
class CategoryController extends _$CategoryController {
  Future<List?> build() async {
    final db = ref.watch(databaseProvider);
    final sync = ref.read(syncProvider);
    final result = await fetchWithFallback(db);
    if (sync != null) sync.publish(result);
    return result;
  }
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["controller.dart"])
    assert "disposed-provider-ref-after-await" not in _roots(result)


def test_reentrant_loader_without_request_identity_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Panel.tsx"
    source.write_text(
        """
const load = async (refresh = false) => {
  setLoading(true);
  const rows = await listRows();
  setRows(rows);
  setLoading(false);
};
useEffect(() => { load(); }, []);
<button onClick={() => load(true)} />
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["Panel.tsx"])
    assert "superseded-request-publishes-component-state" in _roots(result)


def test_reentrant_loader_with_request_identity_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Panel.tsx"
    source.write_text(
        """
const loadRequestIdRef = useRef(0);
const load = async (refresh = false) => {
  const requestId = ++loadRequestIdRef.current;
  setLoading(true);
  const rows = await listRows();
  if (loadRequestIdRef.current !== requestId) return;
  setRows(rows);
  setLoading(false);
};
useEffect(() => { load(); }, []);
<button onClick={() => load(true)} />
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["Panel.tsx"])
    assert "superseded-request-publishes-component-state" not in _roots(result)


def test_session_effect_dispatch_after_await_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "layout.tsx"
    source.write_text(
        """
const { loggedIn, user } = useAppSelector((state) => state.authReducer);
const refresh = async () => {
  const values = await fetchValues();
  dispatch({ type: 'SET_VALUES', payload: values });
};
useEffect(() => {
  refresh();
}, [user]);
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["layout.tsx"])
    assert "stale-session-closure-publishes-after-await" in _roots(result)


def test_session_effect_live_ref_guard_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "layout.tsx"
    source.write_text(
        """
const { loggedIn, user } = useAppSelector((state) => state.authReducer);
const loggedInRef = useRef(loggedIn);
useEffect(() => { loggedInRef.current = loggedIn; }, [loggedIn]);
const refresh = async () => {
  const values = await fetchValues();
  if (!loggedInRef.current) return;
  dispatch({ type: 'SET_VALUES', payload: values });
};
useEffect(() => {
  refresh();
}, [user]);
        """,
        encoding="utf-8",
    )
    result = run_static_async_publication_review(tmp_path, ["layout.tsx"])
    assert "stale-session-closure-publishes-after-await" not in _roots(result)
