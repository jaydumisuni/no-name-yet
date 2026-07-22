# GitHub Actions evidence preservation

Sergeant does not use GitHub Actions storage as its only memory.

The storage warning received on 2026-07-22 triggered a preserve-first response. No existing Actions artifact or workflow run is authorized for deletion by this change.

## Authority rule

An Actions artifact may be considered for deletion only after all of the following are independently proven:

1. its complete bytes were copied to approved durable storage;
2. the durable copy has the same byte length and SHA-256 digest;
3. the source repository, workflow run, exact head SHA, artifact name and original expiry are recorded when available;
4. the durable copy can be downloaded and replayed;
5. its learning, failure, proof and provenance value has been classified;
6. another retained artifact is confirmed to be content-equivalent when deletion is proposed as deduplication;
7. an explicit owner-authorized cleanup manifest names the exact artifact ID.

Unknown, malformed, missing, expired or unclassified evidence fails closed and remains non-deletable.

Deleting a workflow run is stricter than deleting one artifact because it can erase every artifact and the run-level execution record. Workflow-run deletion therefore requires a separate explicit authorization and is never inferred from artifact deduplication.

## What must remain durable

- accepted detectors, tests and generalized rules;
- blind-before-learning records;
- rejected lessons and false-positive controls;
- Teacher, Prosecutor and Defender outputs;
- transfer, holdout and campaign evidence;
- exact source and commit provenance;
- negative attempts and unique failures;
- Main Review and release proof bundles;
- release packages until replaced by verified registry and release assets;
- screenshots, runtime logs and reports that establish a unique claim.

## What may later become a cleanup candidate

Only after the authority rule is satisfied:

- byte-identical package builds from the same commit;
- repeated successful logs whose content is already retained;
- superseded screenshots with a verified canonical copy;
- transient inter-job payloads that contain no unique evidence;
- duplicated proof bundles with matching content digests.

A filename, similar size, successful conclusion or newer run is not proof of equivalence.

## First preservation pass

On 2026-07-22, 29 available Sergeant artifacts totaling 13,772,291 bytes were copied into the private `Sergeant Durable Evidence` Google Drive hierarchy. This included:

- the exact `0.4.1` release-candidate artifacts at head `e5d81856b53beb68b7e04cf2246e64ef7e4624b8`;
- controlled self-learning week-one run 9 and PR #131 proof outputs;
- model-free transfer 30, 32, 33 and 34 evidence;
- retained failed and negative attempts;
- the available PR #132 test output.

The public digest ledger is stored at `evidence/actions/2026-07-22-preservation-ledger.json`. The private recovery ledger records the corresponding Drive folders and is stored beside the durable copies.

## Recovery replay

Every one of the 29 durable Drive copies was subsequently downloaded again. The downloaded byte lengths and SHA-256 digests matched the preservation ledger for all 13,772,291 bytes:

```text
Artifacts replayed: 29
Digest matches:     29
Size matches:       29
Failures:            0
```

The replay result is recorded at `evidence/actions/2026-07-22-recovery-replay.json` and is validated against the original preservation ledger by `validate_recovery_replay`.

Successful recovery replay proves that the preserved copies can be retrieved intact. It does not prove that two different artifacts are semantically redundant, classify their learning value, or authorize deletion.

## Operational sequence

```text
Inventory
→ download complete bytes
→ calculate SHA-256
→ copy to durable storage
→ verify byte length
→ record provenance and location
→ recovery replay
→ classify duplicate or unique
→ owner-authorized cleanup manifest
→ delete exact artifact only
```

The recovery-replay stage is complete for these 29 items. The cleanup count remains zero because content-equivalence classification and an owner-authorized exact-artifact cleanup manifest do not exist.
