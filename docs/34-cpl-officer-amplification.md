# Cpl Officer Amplification

Cpl is Sergeant's senior field-reasoning officer. Cpl does not replace the permanent squad.

Every permanent officer retains:

- universal officer training;
- permanent doctrine and specialist responsibility;
- mission-specific Armoury loadouts;
- evidence and confidence obligations;
- its own officer report.

Cpl adds a higher field-command reasoning layer:

- shared grounded mission intelligence for every deployed officer;
- deterministic decomposition of specialist support assignments;
- replaceable model-powered bots attached to matching permanent officers;
- model rotation and role-specific model selection;
- context, retry, fallback, and completion control;
- auditable return of supported findings to Sergeant.

Current Cpl support mapping:

| Support specialty | Permanent officer |
| --- | --- |
| Correctness | Engineer |
| Architecture | Engineer |
| Tests and contracts | Engineer |
| Security | Medic |
| Performance and concurrency | Mechanic |

The general Cpl pass is shared field intelligence. It benefits the whole deployed squad. Targeted support bots deepen the relevant permanent officer's investigation.

The command relationship is:

```text
Sergeant commands.
Cpl directs and amplifies the field operation.
Permanent officers own their specialties.
Models power Cpl-directed support bots.
The Armoury equips the officers and bots.
Hermes delivers the final evidence accurately.
```

A model is never an officer. A support bot is never allowed to impersonate Cpl or replace the permanent officer to which it is attached.

This change preserves the existing Cpl provider routing, grounding, adaptive depth, fallback behavior, and compatibility aliases. It changes the ownership interpretation of specialist passes so the current reasoning machinery strengthens the established squad instead of collapsing the squad into Cpl.
