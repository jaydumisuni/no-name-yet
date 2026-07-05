# Battle Test Fixture: psf/requests#7502

Repository: `psf/requests`

Pull request: https://github.com/psf/requests/pull/7502

Title: Fix `_encode_files` detection for `__getattr__`-based file wrappers

Outcome: merged

## Why this fixture matters

This PR is a useful Sergeant battle-test candidate because it includes real review pressure, author responses, and final approval.

Signals captured:

- Real merged PR
- Real diff fetched
- Real issue and review comments fetched
- Maintainer requested changes
- Author responded to inline review comments
- Maintainer later approved

## Diff summary

Changed files:

- `src/requests/models.py`
- `tests/test_requests.py`

Core change:

- `_encode_files` now accepts file-like wrappers that proxy `read` through `__getattr__` by using `hasattr(fp, "read")` alongside the existing protocol check.

Test change:

- Adds `test_post_named_tempfile` to verify `NamedTemporaryFile` can be posted through `files`.

## Human review signals

Maintainer feedback focused on test quality rather than core implementation:

- Duplicate/overlapping tests should be removed or parameterized.
- Test inputs should be narrowed to the behavior being verified.
- `files` alone was enough; extra `data`/`params` would blur test intent.

Author response accepted the simplification direction.

Final review was approved.

## Expected Sergeant comparison target

A strong Sergeant review should notice:

- The implementation is small and targeted.
- The test is behavior-focused and covers the regression.
- Additional tests may be redundant if they cover the same wrapper behavior.
- Test intent should stay narrow and avoid unrelated request parameters.
- Risk is low after simplification and approval.

Expected high-level verdict after final iteration: `PASS` or `TRUSTED_WITH_WATCH`.

Expected finding before simplification: `NEEDS WORK` for test clarity/redundancy, not for core implementation correctness.
