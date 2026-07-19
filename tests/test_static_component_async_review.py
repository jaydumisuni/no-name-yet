from __future__ import annotations

from pathlib import Path

from main_review.static_component_async_review import run_static_component_async_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_async_callback_state_after_await_without_lifetime_guard_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "CodeBlock.tsx"
    source.write_text(
        """
export function CodeBlock() {
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const runCodeAsync = useCallback(async () => {
    setLoading(true);
    try {
      const data = await runCode(code, language);
      setOutput(data.output);
    } catch (error) {
      setOutput(String(error));
    } finally {
      setLoading(false);
    }
  }, [code, language]);
  return <button onClick={runCodeAsync}>Run</button>;
}
        """,
        encoding="utf-8",
    )
    result = run_static_component_async_review(tmp_path, ["CodeBlock.tsx"])
    assert "component-async-publication-after-unmount" in _roots(result)


def test_mounted_guard_before_post_await_state_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "CodeBlock.tsx"
    source.write_text(
        """
export function CodeBlock() {
  const [output, setOutput] = useState('');
  const isMountedRef = useRef(true);
  useEffect(() => () => { isMountedRef.current = false; }, []);
  const runCodeAsync = useCallback(async () => {
    const data = await runCode(code, language);
    if (!isMountedRef.current) return;
    setOutput(data.output);
  }, [code, language]);
  return <button onClick={runCodeAsync}>Run</button>;
}
        """,
        encoding="utf-8",
    )
    result = run_static_component_async_review(tmp_path, ["CodeBlock.tsx"])
    assert "component-async-publication-after-unmount" not in _roots(result)


def test_aborted_guard_before_post_await_state_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Runner.tsx"
    source.write_text(
        """
export function Runner() {
  const [output, setOutput] = useState('');
  const run = useCallback(async () => {
    const controller = new AbortController();
    const data = await execute({ signal: controller.signal });
    if (controller.signal.aborted) return;
    setOutput(data.output);
  }, []);
  return <button onClick={run}>Run</button>;
}
        """,
        encoding="utf-8",
    )
    result = run_static_component_async_review(tmp_path, ["Runner.tsx"])
    assert "component-async-publication-after-unmount" not in _roots(result)


def test_async_utility_without_react_state_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "api.ts"
    source.write_text(
        """
export const load = async () => {
  const response = await fetch('/api/data');
  return response.json();
};
        """,
        encoding="utf-8",
    )
    result = run_static_component_async_review(tmp_path, ["api.ts"])
    assert not result["findings"]
