# Tier 3 Evidence Consensus

Tier 3 lets Sergeant use second opinions without becoming dependent on them.

External tools are evidence providers, not authorities.

## Supported evidence shape

Apps may pass `external_providers` through the app bridge:

```python
{
    "source": "CodeRabbit",
    "verdict": "NEEDS WORK",
    "evidence": [
        {
            "message": "Client route has no matching server route.",
            "path": "src/client.js",
            "confidence": 0.75,
        }
    ],
}
```

## Classifications

Sergeant classifies external findings as:

- `correct`
- `investigate`
- `suggestion`
- `context`
- `internal`

## Rule

Sergeant owns the decision. External tools are witnesses whose evidence is weighed, challenged, and classified.