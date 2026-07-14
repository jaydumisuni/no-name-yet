# Reviewer Head-to-Head Comparison

Sergeant can compare its review with another reviewer on the same frozen pull-request head.

The comparison is intentionally conservative:

- both reports remain separate evidence sources;
- equivalent findings are matched by changed path, nearby line, category and textual evidence;
- unmatched findings remain visible on the correct side;
- walkthroughs, summaries and nitpicks do not count as actionable defects;
- comment volume does not determine reviewer quality;
- no winner is declared without repository-backed adjudication.

## File comparison

Export the external reviewer comments through Sergeant's existing ingestion format, then run:

```text
sergeant-compare \
  --sergeant-packet build/sergeant-review.json \
  --reference-review build/reference-review.json \
  --reference-name "Reference reviewer" \
  --output build/reviewer-comparison.json \
  --markdown-output build/reviewer-comparison.md \
  --pretty
```

## Live pull-request comparison

The live mode uses Sergeant's existing GET-only, host-validated GitHub evidence boundary:

```text
sergeant-compare \
  --sergeant-packet build/sergeant-review.json \
  --live-repository owner/repository \
  --live-pr 123 \
  --reference-name "Reference reviewer" \
  --reference-author reviewer-login \
  --expected-head-sha <frozen-head-sha> \
  --output build/reviewer-comparison.json \
  --markdown-output build/reviewer-comparison.md \
  --pretty
```

`--expected-head-sha` blocks the comparison when the pull request changes after either review was captured. Inline comments anchored to older commit IDs are excluded from the frozen comparison.

The optional GitHub token is read from `GITHUB_TOKEN` by default. The token is not placed in the comparison artifact.

## Side-by-side output

The report contains:

- actionable finding count per reviewer;
- matched findings shown side by side;
- findings unique to Sergeant;
- findings unique to the reference reviewer;
- overlap rate;
- source and frozen-head metadata;
- optional adjudication summaries.

A match means only that both reviewers appear to describe the same issue. It does not establish that the issue is valid.

Sergeant findings are collected from every verdict-bearing layer: review intelligence, diff review, repository review and Cpl findings. This prevents the comparison from hiding the finding that actually controlled Sergeant's verdict.

## Adjudication

An optional adjudication file can classify findings as:

- `confirmed`;
- `suggestion`;
- `false_positive`;
- `duplicate`;
- `uncertain`.

Example:

```json
{
  "decisions": [
    {
      "reviewer": "Sergeant",
      "finding_id": "sergeant-example",
      "status": "confirmed"
    },
    {
      "reviewer": "Reference reviewer",
      "finding_id": "reference-example",
      "status": "false_positive"
    }
  ]
}
```

Finding IDs are derived from stable evidence such as comment URLs, paths and message content instead of list position.

The comparator can report verified precision for adjudicated findings. Recall remains undefined until the complete verified defect set is known.

## Trust boundary

The external report does not enter Sergeant's verdict consensus during blind review. It is introduced only after Sergeant's packet has been frozen.

Verified external findings may later enter the governed learning process through the existing review-ingestion and decision-workspace controls. Unverified reviewer opinions do not become permanent knowledge.

## Workflow assurance

Workflow: `.github/workflows/reviewer-comparison-proof.yml`

- **Purpose:** prove the comparison tests, source command and installed-wheel command on the same change.
- **Permissions:** GitHub permissions are limited to `contents: read`; checkout credential persistence is disabled.
- **Secrets:** the proof workflow does not require or export a provider key, GitHub write token or private reviewer credential.
- **Rollback:** remove the isolated workflow and the `sergeant-compare` entry point without changing the existing reviewer, Cpl, Command Center or standalone service.
- **Proof:** the workflow runs the focused comparison suite, builds the wheel, installs it in a clean virtual environment outside the source tree and executes `sergeant-compare --help`.
