# Clean Clone Proof

Clean-clone proof is the verification step after implementation and review.

It confirms that the repository works from a fresh checkout, not only in the developer's existing environment.

## Standard workflow

```bash
git clone <repo-url> main-review-clean-proof
cd main-review-clean-proof
python -m pip install --upgrade pip pytest
python -m pip install -e .
pytest -q
main-review scan --pretty
main-review evidence --pretty
main-review review --pretty
main-review verify-standard --pretty
```

## Expected result

- tests pass
- CLI imports successfully
- repository scan returns JSON
- evidence command returns JSON
- review command returns JSON
- verification command returns `verified` or a clearly explained `partial`

## Rule

CI green is not the same as clean-clone proof.

CI proves the automated test path.

Clean clone proves a fresh user/developer path.

## When to run

Run clean-clone proof after:

- major feature batches
- reviewer architecture changes
- CLI command changes
- package/import changes
- release candidate freeze

## What counts as failure

Any of these fail the proof:

- missing dependency
- broken import
- missing package file
- CLI command unavailable
- docs claiming behavior that commands do not provide
- test suite fails
- verification standard reports missing required evidence
