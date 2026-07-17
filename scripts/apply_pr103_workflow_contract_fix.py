from pathlib import Path

path = Path(".github/workflows/cloudflare-full-council-certification.yml")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "      - 'tests/test_cloudflare_incremental_certification.py'\n      - 'tests/test_cloudflare_usage_governor.py'",
    "      - 'tests/test_cloudflare_incremental_certification.py'\n      - 'tests/test_cloudflare_certification_workflow_contract.py'\n      - 'tests/test_cloudflare_usage_governor.py'",
    1,
)
text = text.replace(
    "            tests/test_cloudflare_incremental_certification.py \\\n            tests/test_cloudflare_mission_qualification.py \\",
    "            tests/test_cloudflare_incremental_certification.py \\\n            tests/test_cloudflare_certification_workflow_contract.py \\\n            tests/test_cloudflare_mission_qualification.py \\",
    1,
)
old = '''          artifact_id="$(${GH_TOKEN:+gh api "/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=cloudflare-full-council-ledger&per_page=100" --jq '.artifacts | map(select(.expired == false)) | sort_by(.created_at) | reverse | .[0].id // empty' 2>/dev/null || true})"'''
new = '''          artifact_id="$(gh api "/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=cloudflare-full-council-ledger&per_page=100" --jq '.artifacts | map(select(.expired == false)) | sort_by(.created_at) | reverse | .[0].id // empty' 2>/dev/null || true)"'''
if old not in text:
    raise SystemExit("artifact lookup block missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
