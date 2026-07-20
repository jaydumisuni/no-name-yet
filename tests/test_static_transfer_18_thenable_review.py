from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_18_review import run_static_transfer_18_review


ROOT = "thenable-request-body-validated-before-resolution"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_http_wrapper_must_resolve_thenable_body_before_validation(tmp_path: Path) -> None:
    source = tmp_path / "defineResource.ts"
    source.write_text(
        '''
function wrapStaticVerb(original: Function, compiled: CompiledVerb): Function {
  const { bodyFragment, hasBody } = compiled;
  return function (target: any, ...rest: any[]) {
    const issues: ValidationIssue[] = [];
    if (hasBody && bodyFragment) rest[0] = validateBody(bodyFragment, rest[0], issues);
    if (issues.length) throw new ValidationError(issues);
    return original.call(this, target, ...rest);
  };
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["defineResource.ts"])

    assert ROOT in _roots(result)


def test_thenable_branch_before_validation_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "defineResource.ts"
    source.write_text(
        '''
function wrapStaticVerb(original: Function, compiled: CompiledVerb): Function {
  const { bodyFragment, hasBody } = compiled;
  return function (target: any, ...rest: any[]) {
    const body = rest[0];
    if (hasBody && bodyFragment && body && typeof body.then === "function") {
      return body.then((resolved: any) => {
        rest[0] = validateBody(bodyFragment, resolved, []);
        return original.call(this, target, ...rest);
      });
    }
    if (hasBody && bodyFragment) rest[0] = validateBody(bodyFragment, body, []);
    return original.call(this, target, ...rest);
  };
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["defineResource.ts"])

    assert ROOT not in _roots(result)


def test_plain_non_http_validator_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "validate.ts"
    source.write_text(
        '''
function validateRecord(rest: unknown[]) {
  return validateBody(schema, rest[0], []);
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_18_review(tmp_path, ["validate.ts"])

    assert ROOT not in _roots(result)
