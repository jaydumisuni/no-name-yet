from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_20_review import run_static_transfer_20_review


PYTHON_ROOT = "hash-contract-collapses-field-values-to-runtime-type"
RUST_ROOT = "compatibility-guard-applied-to-only-one-shared-diagnostic-path"
TS_ROOT = "stable-chunk-identity-omits-emitted-css-sidecars"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_hashing_field_runtime_type_collapses_distinct_values(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "value.py",
        '''
from typing import Literal

class SchemaMode:
    mode: Literal["validation", "serialization"] | None = None

    def __hash__(self) -> int:
        return hash(type(self.mode))
''',
    )

    result = run_static_transfer_20_review(tmp_path, ["value.py"])

    assert PYTHON_ROOT in _roots(result)


def test_hashing_field_value_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "value.py",
        '''
class SchemaMode:
    mode: str | None = None

    def __hash__(self) -> int:
        return hash(self.mode)
''',
    )

    result = run_static_transfer_20_review(tmp_path, ["value.py"])

    assert PYTHON_ROOT not in _roots(result)


def test_hashing_instance_type_for_class_identity_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "identity.py",
        '''
class Identity:
    def __hash__(self) -> int:
        return hash(type(self))
''',
    )

    result = run_static_transfer_20_review(tmp_path, ["identity.py"])

    assert PYTHON_ROOT not in _roots(result)


def test_compatibility_guard_on_only_one_shared_diagnostic_caller(tmp_path: Path) -> None:
    relative = "rule.rs"
    _write(
        tmp_path,
        relative,
        '''
fn alias_type(checker: &Checker, type_vars: &[TypeVar]) {
    create_diagnostic(checker, type_vars);
}

fn alias_annotation(checker: &Checker, type_vars: &[TypeVar]) {
    if type_vars.iter().any(|type_var| type_var.default.is_some())
        && !is_type_var_default_enabled(checker.settings())
    {
        return;
    }
    create_diagnostic(checker, type_vars);
}

fn create_diagnostic(checker: &Checker, type_vars: &[TypeVar]) {
    checker.report_diagnostic(Diagnostic::new(type_vars));
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [relative])

    assert RUST_ROOT in _roots(result)


def test_compatibility_guard_centralized_in_shared_helper_is_clean(tmp_path: Path) -> None:
    relative = "rule.rs"
    _write(
        tmp_path,
        relative,
        '''
fn alias_type(checker: &Checker, type_vars: &[TypeVar]) {
    create_diagnostic(checker, type_vars);
}

fn alias_annotation(checker: &Checker, type_vars: &[TypeVar]) {
    create_diagnostic(checker, type_vars);
}

fn create_diagnostic(checker: &Checker, type_vars: &[TypeVar]) {
    if (checker.target_version() < PythonVersion::PY313
        || !is_type_var_default_enabled(checker.settings()))
        && type_vars.iter().any(|type_var| type_var.default.is_some())
    {
        return;
    }
    checker.report_diagnostic(Diagnostic::new(type_vars));
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [relative])

    assert RUST_ROOT not in _roots(result)


def test_single_diagnostic_entry_point_is_clean(tmp_path: Path) -> None:
    relative = "rule.rs"
    _write(
        tmp_path,
        relative,
        '''
fn alias_annotation(checker: &Checker, type_vars: &[TypeVar]) {
    if type_vars.iter().any(|type_var| type_var.default.is_some())
        && !is_type_var_default_enabled(checker.settings())
    {
        return;
    }
    create_diagnostic(checker, type_vars);
}

fn create_diagnostic(checker: &Checker, type_vars: &[TypeVar]) {
    checker.report_diagnostic(Diagnostic::new(type_vars));
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [relative])

    assert RUST_ROOT not in _roots(result)


def test_import_map_omits_emitted_css_sidecar_identity(tmp_path: Path) -> None:
    html = "packages/build/html.ts"
    css = "packages/build/css.ts"
    _write(
        tmp_path,
        html,
        '''
export function getImportMap(bundle, config) {
  const asset = bundle["importmap.json"]
  const content = JSON.parse(asset.source)
  const mapping = Object.fromEntries(
    Object.entries(content.imports).map(([key, value]) => [key, value]),
  )
  return { asset, mapping }
}
''',
    )
    _write(
        tmp_path,
        css,
        '''
export function cssPostPlugin(config) {
  return {
    renderChunk(code, chunk: RenderedChunk) {
      // Emit the extracted CSS sidecar for this rendered chunk.
      const chunkCSS = collectCss(chunk)
      this.emitFile({ type: "asset", name: chunk.fileName, source: chunkCSS })
      if (config.build.chunkImportMap) {
        getImportMap(this.getBundle(), config)
      }
    },
  }
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [html, css])

    assert TS_ROOT in _roots(result)


def test_import_map_tracks_and_maps_emitted_css_sidecar_is_clean(tmp_path: Path) -> None:
    html = "packages/build/html.ts"
    css = "packages/build/css.ts"
    _write(
        tmp_path,
        html,
        '''
export function getImportMap(bundle, config) {
  const asset = bundle["importmap.json"]
  const content = JSON.parse(asset.source)
  const mapping = Object.fromEntries(
    Object.entries(content.imports).map(([key, value]) => [key, value]),
  )
  return { asset, content, mapping }
}
''',
    )
    _write(
        tmp_path,
        css,
        '''
export function cssPostPlugin(config) {
  const chunkCssReferences = new Map<string, string>()
  return {
    renderChunk(code, chunk: RenderedChunk) {
      const chunkCSS = collectCss(chunk)
      const referenceId = this.emitFile({
        type: "asset",
        name: chunk.fileName,
        source: chunkCSS,
      })
      chunkCssReferences.set(chunk.fileName, referenceId)
      if (config.build.chunkImportMap) {
        const importMap = getImportMap(this.getBundle(), config)
        importMap.content.imports[chunk.fileName.replace(/\.js$/, ".css")] =
          this.getFileName(referenceId)
      }
    },
  }
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [html, css])

    assert TS_ROOT not in _roots(result)


def test_plain_css_asset_emission_without_import_map_feature_is_clean(tmp_path: Path) -> None:
    relative = "css.ts"
    _write(
        tmp_path,
        relative,
        '''
export function emitStyles(chunk: RenderedChunk) {
  const chunkCSS = collectCss(chunk)
  return this.emitFile({ type: "asset", source: chunkCSS })
}
''',
    )

    result = run_static_transfer_20_review(tmp_path, [relative])

    assert TS_ROOT not in _roots(result)
