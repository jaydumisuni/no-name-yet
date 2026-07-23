# Blind benchmark: Lumi extension token-origin boundary

This temporary benchmark branch tests Sergeant against a real pre-fix commit from `jaydumisuni/lumi-dm`.

Blind target:

```text
repository: jaydumisuni/lumi-dm
commit: 8f63f832112a2e0772e954c3e0319109ce21b6a9
file: browser-extension/security-shim.js
```

The fixing commit and defect classification are intentionally omitted from this branch until the first Sergeant report is frozen. The branch must not be merged into `main`; it exists only to trigger and preserve the blind benchmark run.