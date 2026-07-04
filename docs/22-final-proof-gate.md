# Final Proof Gate

The Final Proof Gate is the last automated confidence check before accepting the repository state.

It combines:

```text
main-review review
  +
main-review verify-standard
  ↓
main-review final-proof
```

## Pass condition

Final proof passes only when:

- repository review verdict is `PASS`
- THETECHGUY verification status is `verified`

If either side fails, the command exits non-zero by default.

## CLI

```bash
main-review final-proof --pretty
```

To inspect JSON without failing the shell:

```bash
main-review final-proof --no-fail --pretty
```

## Why this matters

This prevents confidence from being based only on a green test run.

The final proof gate checks both code state and engineering-standard evidence.

## Current limitation

This still cannot force CodeRabbit to review when CodeRabbit is rate-limited.

When CodeRabbit is unavailable, Main Review must record that honestly and proceed using:

- CI proof
- clean-clone proof
- built-in evidence providers
- THETECHGUY verification standard
- open-source reviewer patterns already documented

The reviewer should never pretend an external review happened when it did not.
