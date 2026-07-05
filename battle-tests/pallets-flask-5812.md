# Battle Test Fixture: pallets/flask#5812

Repository: `pallets/flask`

Pull request: https://github.com/pallets/flask/pull/5812

Title: merge app and request context

Outcome: merged

## Why this fixture matters

This is a large architecture-level framework change. It is useful for testing whether Sergeant can review beyond small diffs.

Signals captured:

- Real merged PR
- 36 changed files
- Large documentation and implementation rewrite
- Context lifecycle and proxy behavior changes
- Backward-compatibility/deprecation concerns
- External app compatibility testing before merge
- Later follow-up note about a concurrency/push-counter issue

## Review context

The PR merged Flask's request context behavior into the app context model. The author stated that user-facing APIs should remain mostly unchanged while internals become simpler.

The PR also explicitly acknowledged upgrade risk for projects that relied on discouraged testing patterns around `app.app_context()` and test-client requests.

Community validation mattered: a large downstream app was tested against the branch and passed unchanged before merge.

A later follow-up note mentioned `copy_current_request_context` and a context copy being reused across threads causing push counter issues.

## Expected Sergeant comparison target

A strong Sergeant review should notice:

- This is an architecture change, not just cleanup.
- Documentation updates are part of the implementation contract.
- Deprecation aliases and migration behavior are important.
- Tests must cover context push/pop lifecycle, teardown ordering, request/app proxy availability, shell/testing behavior, and preserved contexts.
- Compatibility testing against a real downstream app is strong evidence but does not replace focused internal regression tests.
- `copy_current_request_context`, streaming, and concurrency-style context reuse are high-risk areas.
- The later follow-up suggests Sergeant should flag copied-context reuse and push-counter semantics as a regression risk.

Expected high-level verdict before downstream and focused compatibility evidence: `NEEDS WORK`.

Expected high-level verdict after evidence and follow-up fixes: `PASS_WITH_WATCH`.
