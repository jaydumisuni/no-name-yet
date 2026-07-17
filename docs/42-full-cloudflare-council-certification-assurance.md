# Full Cloudflare council certification assurance

Assured path: `.github/workflows/cloudflare-full-council-certification.yml`

## Purpose

This workflow proves every unique Cloudflare Workers AI member in Sergeant's public
council roster without restarting the whole exam after a quota interruption.

Each member receives one role-appropriate mission:

- six reasoning/coding members complete the grounded security-officer mission;
- Granite 4.0 H Micro completes a Scout extraction mission with exact values, file
  coverage and line evidence.

A successful role mission also proves structured transport. No separate handshake
call is required.

## Two-stage workflow

### Candidate validation

`validate-candidate` checks out the pull-request head, installs it and runs focused
tests without Cloudflare provider configuration.

### Approved live certification

`certify-approved-candidate` runs only when:

1. repository variable `SERGEANT_CLOUDFLARE_LIVE_CERTIFICATION_ENABLED` is `true`;
2. GitHub environment `sergeant-cloudflare-certification` authorizes the job.

Repository administrators must configure that environment with appropriate reviewer
and deployment restrictions. Until both controls exist, the live job is skipped.

After approval, the exact candidate code runs with the provider configuration during
only the route-status and certification steps. Environment approval is the trust
decision. The final artifact scan confirms that configured values are absent from
saved evidence; it does not make a broader claim about runtime access.

## Resumable ledger

The workflow preserves:

- `full-council-ledger.json` — member proof by exact commit and contract version;
- `cloudflare-usage-state.json` — conservative daily reservations and circuit state.

Passing members from the same exact head and contract are skipped. A changed head or
contract creates fresh member proof. The ledger is saved after each member so a
runner, budget or provider interruption preserves completed work.

## Quota and budget behavior

Sergeant reserves a conservative model-specific estimate before each inference. The
public controls are:

- `SERGEANT_CLOUDFLARE_DAILY_BUDGET_NEURONS`;
- `SERGEANT_CLOUDFLARE_SAFETY_RESERVE_NEURONS`;
- `SERGEANT_CLOUDFLARE_UNKNOWN_MODEL_RESERVATION_NEURONS`;
- `SERGEANT_CLOUDFLARE_USAGE_STATE`;
- `SERGEANT_CLOUDFLARE_USAGE_GOVERNOR`.

If a request would exceed the local budget, Sergeant stops before network access.
When Cloudflare returns allocation-specific code `4006` or an explicit daily-
allocation message, Sergeant:

1. opens the daily circuit;
2. does not retry another request shape;
3. does not continue through the roster;
4. records the member as quota-blocked, not failed;
5. saves the ledger for later continuation.

A generic HTTP `429` remains a normal provider throttle and does not open the all-day
allocation circuit.

## State integrity

Usage load, reservation and save are serialized across processes using an atomic
lock file. Writes use unique temporary files followed by atomic replacement.

Budget and quota stops carry the UTC day that caused them. A later UTC day clears the
stop while retaining same-head member proof.

## Permissions and model authority

The workflow declares `contents: read` and `actions: read`. Checkout uses
`persist-credentials: false`. It cannot push commits, alter pull requests, publish or
merge.

Models receive fixed bounded fixtures. They have no repository-write, merge,
deployment, shell or tool authority.

## Exact roster gate

Completion requires exactly these seven IDs, with no missing, extra or substituted
member:

- `@cf/zai-org/glm-4.7-flash`;
- `@cf/qwen/qwen2.5-coder-32b-instruct`;
- `@cf/ibm-granite/granite-4.0-h-micro`;
- `@cf/openai/gpt-oss-120b`;
- `@cf/moonshotai/kimi-k2.7-code`;
- `@cf/qwen/qwen3-30b-a3b-fp8`;
- `@cf/openai/gpt-oss-20b`.

## Proof requirements

The change is acceptable only when:

1. focused compatibility, incremental-ledger, mission and usage-governor tests pass;
2. the full repository suite and all normal Sergeant proof workflows pass;
3. candidate validation runs without provider configuration;
4. the live job is protected and explicitly enabled;
5. the approved route validates;
6. all seven members have same-head role-mission proof;
7. Granite passes Scout proof and the other six pass officer proof;
8. the exact seven-member set is enforced;
9. saved evidence passes the configured-value scan;
10. tests prove allocation-specific circuit behavior, generic-429 handling, local
    preflight blocking, cross-process accounting, Scout path containment, prompt-
    echo rejection and final structured-answer selection.
11. `tests/test_coderabbit_rematch_regressions.py` proves the rematch roots and
    their clean controls, and the certification workflow both triggers on and
    executes that focused regression module.

The workflow remains incomplete when provider capacity, local budget or protected-
environment approval blocks it. It must resume from the exact-head ledger.

## Rollback and scope

Removing this workflow, its qualification/governor modules and their tests returns to
the already proved two-member baseline. Deterministic Sergeant and non-Cloudflare
routes remain available.

This is direct Sergeant protection only. Shared Hunter/Sergeant accounting and paid-
provider routing remain private future gateway work.
