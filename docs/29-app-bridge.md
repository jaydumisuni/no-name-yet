# Sergeant App Bridge

The app bridge is the stable layer an app can call without depending on Sergeant internals.

## Python usage

```python
from main_review.app_bridge import handle_app_review_request

payload = handle_app_review_request({
    "root": ".",
    "mode": "pull_request",
    "changed_files": ["src/app.py", "tests/test_app.py"],
})
```

## CLI usage

```bash
main-review app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

## Response contract

The bridge returns:

- `ok`
- `service`
- `mode`
- `status`: pass, needs_work, or block
- `action`: APPROVE, COMMENT, or REQUEST_CHANGES
- `confidence`
- `reason`
- `required_actions`
- `quality_score`
- `root_causes`
- `top_findings`
- `markdown`
- `packet`

## Rule

Apps should call the bridge, not Sergeant's internal review modules directly.