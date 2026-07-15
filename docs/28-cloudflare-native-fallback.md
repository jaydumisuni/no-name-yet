# Cloudflare native response fallback

Cloudflare model certification showed that the route and credentials were valid while several models returned response shapes not accepted by Sergeant's OpenAI-compatible parser.

This change adds a Cloudflare-only fallback to the native Workers AI model endpoint when the compatible route returns no parseable text. Generic providers retain their existing behavior and are never redirected to Cloudflare.

The fallback:

- uses the same scoped token and account route;
- sends the same system and user prompts;
- accepts documented `response` envelopes, including Cloudflare API wrapper `result.response`;
- reports only response key shapes when text is missing;
- never includes response bodies, credentials, or account identifiers in errors;
- gives reasoning models a larger but bounded structured-proof budget.

Rollback removes the fallback helpers, model-specific probe budgets, focused tests, and this document. The original OpenAI-compatible route remains intact.