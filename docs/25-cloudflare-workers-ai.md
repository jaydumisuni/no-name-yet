# Cloudflare Workers AI connector

Sergeant can use a user's own Cloudflare Workers AI account without storing the
credential in the public repository. The connector exposes a loopback-only
OpenAI-compatible gateway, so the existing Cpl reasoning council, VS Code,
JetBrains and other Sergeant clients can use the same local route.

## What remains public

The repository contains:

- the provider-neutral Cpl council;
- the loopback Cloudflare gateway;
- model-roster and structured-output proof commands;
- deterministic and multi-model benchmark contracts;
- no THETECHGUY account IDs, tokens or private model-routing policy.

Every user supplies their own Cloudflare Account ID and scoped API token. Model
selection is optional: `SERGEANT_CLOUDFLARE_MODELS` overrides the built-in public
starter roster when a user wants different models.

## Create a scoped Workers AI token

In Cloudflare, open **Workers AI → Use REST API**, create a Workers AI API token,
and copy the Account ID. Cloudflare documents `Workers AI - Read` and
`Workers AI - Edit` permissions for a custom token.

Store the values in environment variables. Do not commit them to `.env`, Git,
issue comments or workflow logs.

PowerShell:

```powershell
$env:SERGEANT_CLOUDFLARE_ACCOUNT_ID="your-account-id"
$env:SERGEANT_CLOUDFLARE_API_TOKEN="your-scoped-token"
$env:SERGEANT_CLOUDFLARE_MODELS="@cf/zai-org/glm-4.7-flash,@cf/openai/gpt-oss-120b,@cf/moonshotai/kimi-k2.7-code"
```

Bash:

```bash
export SERGEANT_CLOUDFLARE_ACCOUNT_ID="your-account-id"
export SERGEANT_CLOUDFLARE_API_TOKEN="your-scoped-token"
export SERGEANT_CLOUDFLARE_MODELS="@cf/zai-org/glm-4.7-flash,@cf/openai/gpt-oss-120b,@cf/moonshotai/kimi-k2.7-code"
```

Roster order matters. Sergeant starts with the first model and recruits later
members only when the council has work for them. The public starter roster puts
GLM Flash first as the efficient reasoning route, while GPT-OSS and Kimi remain
available for independent confirmation and harder coding investigations.

The model roster is explicit. Sergeant does not silently add a newly released
model to the council or spend against it.

## Check configuration

```bash
sergeant-cloudflare --pretty status --require
```

The status packet reports whether the Account ID and token are present but never
prints either value.

## Prove every configured model

```bash
sergeant-cloudflare --pretty test-models --require
```

This makes one small structured-output call to each configured model. A model is
not considered ready merely because an HTTP endpoint responded: it must return
the complete structured proof contract.

## Run the local gateway

```bash
sergeant-cloudflare --pretty gateway
```

The gateway binds to a loopback address only and defaults to `127.0.0.1:8082`.
It exposes:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

It refuses models outside the configured roster, requires a non-empty messages
array and does not support streaming in the first release. Network binding is
not available in this release because an unauthenticated remote gateway could
expose the operator's Cloudflare quota and billing account.

In another terminal, print the environment for Sergeant:

```bash
sergeant-cloudflare env --shell powershell
# or
sergeant-cloudflare env --shell bash
```

Then run normal Sergeant commands. The existing Cpl router discovers the model
roster from the local `/v1/models` endpoint.

## Prove a real multi-model council

```bash
sergeant-cloudflare --pretty council-proof . \
  --files "main_review/example.py,tests/test_example.py" \
  --output build/cloudflare-council-proof.json
```

A valid proof requires:

- at least two configured models;
- completed real model passes;
- more than one distinct model in the result;
- `true_model_independence: true`;
- a complete council;
- no provider errors;
- no unresolved final gaps.

A complete council may correctly return `PASS`, `NEEDS WORK` or `BLOCK`. The
proof certifies that the council operated correctly; it does not force the code
under review to receive a passing verdict.

## Cost and privacy boundary

Cloudflare usage is charged to the user's Cloudflare account and subject to the
current Workers AI allocation and pricing. Sergeant does not hide model calls or
silently fall back to another paid provider.

The first model is the default worker. Later roster members are not called merely
because they are configured: Cpl recruits them when disagreement, missing proof,
independent confirmation or another unresolved gap requires them.

The gateway forwards OpenAI-compatible JSON submitted by local Sergeant, IDE or
other compatible clients after applying its documented path, size, model,
streaming and messages validation. It does not guarantee that every request was
created by Cpl or contains only repository excerpts. Users and client
integrations are responsible for ensuring the submitted content complies with
the repository's privacy policy and the provider's data-handling policy.

## Future website and IDE connection

The website and IDE account screens will manage the same connector contract:

1. sign in to Sergeant;
2. connect a Cloudflare account or paste a scoped token locally;
3. choose an approved model roster;
4. run connection and benchmark proof;
5. activate that route for website, CLI, VS Code or JetBrains use.

Provider credentials remain separate from the public Sergeant source and from
THETECHGUY's private Hunter routing configuration.
