# Tier 4 Verified Learning Loop

Tier 4 lets Sergeant improve from human-confirmed review outcomes.

It does not blindly memorize every finding. It learns from explicit decisions only.

## Inputs

Apps may pass `human_decisions` through the app bridge:

```python
{
    "finding_index": 0,
    "decision": "accepted",
    "reason": "Human confirmed this route drift is real.",
    "confidence": 0.95,
}
```

Supported decisions include:

- `accepted`
- `correct`
- `fixed`
- `true_positive`
- `rejected`
- `false_positive`
- `intentional`
- `wontfix`
- `learn`
- `lesson`
- `pattern`

## Output

Sergeant produces memory candidates and can optionally write them into `.main-review/memory.json` when `write_learning` is true.

## Rule

Learning must be verified. A review finding becomes memory only after a human-confirmed outcome.