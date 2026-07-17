# Full Cloudflare council workflow assurance

Assured path: `.github/workflows/cloudflare-full-council-certification.yml`

## Purpose

Validate pull-request changes without provider access, then allow a separately
approved exact-head live certification to resume only missing council-member proof.

## Permissions

The workflow has `contents: read` and `actions: read`. Checkout does not persist the
GitHub token. It cannot push, merge, publish or alter pull requests.

## Secrets

Candidate validation receives no Cloudflare secrets. The live job is disabled unless
an explicit repository variable enables it and the protected
`sergeant-cloudflare-certification` environment approves it. Provider values are
supplied only to the approved route-status and certification steps. Saved evidence is
scanned before upload; that scan applies to artifacts and is not treated as proof of
broader runtime isolation.

## Rollback

Disable the live-certification repository variable or remove the workflow. The
already proved deterministic Sergeant and two-member council baseline remain
available. Removing the incremental certification and quota-governor modules returns
to the earlier provider routing behavior.

## Proof

Focused tests cover the exact roster, ledger resumption, daily expiry, prompt-echo
rejection, bounded security matching, path containment, cross-process accounting,
allocation-specific circuit behavior, generic throttling and final JSON selection.
The full repository suite and standard Sergeant workflows must pass. Live completion
requires the exact seven model IDs on one exact head, with a clean evidence artifact.
