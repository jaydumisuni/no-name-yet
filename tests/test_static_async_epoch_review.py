from __future__ import annotations

from pathlib import Path

from main_review.static_async_epoch_review import run_static_async_epoch_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_kotlin_stale_suspend_response_is_reported(tmp_path: Path) -> None:
    (tmp_path / "Api.kt").write_text(
        """
interface Api {
    suspend fun linkStatus(): LinkStatus
}
        """,
        encoding="utf-8",
    )
    source = tmp_path / "ViewModel.kt"
    source.write_text(
        """
private fun startPolling(gen: Long) {
    scope.launch {
        while (isActive) {
            if (!isActive) return@launch
            when (val status = api.linkStatus()) {
                is LinkStatus.Claimed -> {
                    _phase.value = Phase.Claimed(status.deviceName)
                }
            }
        }
    }
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["ViewModel.kt"])
    assert "stale-coroutine-response-after-suspension" in _roots(result)


def test_kotlin_post_suspend_generation_guard_is_clean(tmp_path: Path) -> None:
    (tmp_path / "Api.kt").write_text(
        """
interface Api {
    suspend fun linkStatus(): LinkStatus
}
        """,
        encoding="utf-8",
    )
    source = tmp_path / "ViewModel.kt"
    source.write_text(
        """
private fun startPolling(gen: Long) {
    scope.launch {
        while (isActive) {
            if (!isActive) return@launch
            val status = api.linkStatus()
            if (gen != generation || !isActive) return@launch
            if (status is LinkStatus.Claimed) {
                _phase.value = Phase.Claimed(status.deviceName)
            }
        }
    }
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["ViewModel.kt"])
    assert "stale-coroutine-response-after-suspension" not in _roots(result)


def test_react_effect_without_lifetime_guard_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "index.html"
    source.write_text(
        """
<script>
useEffect(() => {
  if (!partner) return;
  const load = async () => {
    const data = await fetchMessages(partner.id);
    setMessages(data);
  };
  load();
  return () => {
    clearTyping();
  };
}, [partner.id]);
</script>
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["index.html"])
    assert "effect-response-published-after-lifetime-change" in _roots(result)


def test_react_effect_cancel_guard_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "index.html"
    source.write_text(
        """
<script>
useEffect(() => {
  if (!partner) return;
  let cancelled = false;
  const load = async () => {
    const data = await fetchMessages(partner.id);
    if (cancelled) return;
    setMessages(data);
  };
  load();
  return () => {
    cancelled = true;
  };
}, [partner.id]);
</script>
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["index.html"])
    assert "effect-response-published-after-lifetime-change" not in _roots(result)


def test_non_cancellable_second_await_requires_owner_check(tmp_path: Path) -> None:
    source = tmp_path / "banking.js"
    source.write_text(
        """
const banks = new Map();
let bankCtl = null;

async function bankOne(idx) {
  const ctl = new AbortController();
  bankCtl = ctl;
  const blob = await fetchBlob({ signal: ctl.signal });
  const persisted = await bufferTrack(blob);
  if (!persisted) banks.set(idx, blob);
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["banking.js"])
    assert "ownership-token-not-revalidated-after-await" in _roots(result)


def test_owner_check_after_second_await_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "banking.js"
    source.write_text(
        """
const banks = new Map();
let bankCtl = null;

async function bankOne(idx) {
  const ctl = new AbortController();
  bankCtl = ctl;
  const blob = await fetchBlob({ signal: ctl.signal });
  const persisted = await bufferTrack(blob);
  if (bankCtl !== ctl) return;
  if (!persisted) banks.set(idx, blob);
}
        """,
        encoding="utf-8",
    )
    result = run_static_async_epoch_review(tmp_path, ["banking.js"])
    assert "ownership-token-not-revalidated-after-await" not in _roots(result)
