from __future__ import annotations

from pathlib import Path

from main_review.diff_policy import normalize_diff_review
from main_review.diff_review import review_changed_files
from main_review.officer_council import OFFICER_ORDER, run_officer_council
from main_review.offline_investigation import run_offline_investigations


MODELS = (
    "@cf/zai-org/glm-4.7-flash",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/ibm-granite/granite-4.0-h-micro",
    "@cf/openai/gpt-oss-120b",
    "@cf/moonshotai/kimi-k2.7-code",
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/openai/gpt-oss-20b",
)


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _defective_formation(root: Path) -> list[str]:
    workflow = ".github/workflows/certify.yml"
    test_path = "tests/test_certification_workflow_contract.py"
    _write(
        root,
        workflow,
        """name: certify
on:
  pull_request:
    paths:
      - '.github/workflows/certify.yml'
jobs:
  certify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: python -m pip install -e .
      - run: python -m pytest -q tests/test_other.py
        env:
          API_TOKEN: ${{ secrets.API_TOKEN }}
      - run: |
          python - <<'PY'
          payload = {'passed': True}
          assert payload.get('passed') is True
          PY
""",
    )
    _write(
        root,
        "docs/certification-assurance.md",
        """# Assurance

Assured path: `.github/workflows/certify.yml`
Purpose, permissions, secrets, rollback and proof are reviewed.
Focused proof requires `tests/test_certification_workflow_contract.py`.
""",
    )
    _write(
        root,
        test_path,
        "REQUIRED_MODELS = {\n" + "\n".join(f'    "{model}",' for model in MODELS) + "\n}\n",
    )
    _write(
        root,
        "src/cloudflare_cli.py",
        """SECURITY_MARKERS = ('rce', 'auth')

def proof_contract_matches(payload):
    candidates = [payload]
    for key in ('required', 'result'):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    return any(marker in 'source authoring' for marker in SECURITY_MARKERS)
""",
    )
    _write(
        root,
        "src/incremental.py",
        """import json

def stop(ledger):
    ledger['budget_blocked'] = True
    return json.dumps(ledger)
""",
    )
    _write(
        root,
        "src/scout.py",
        """from pathlib import Path

def load(root, file):
    source = Path(root) / file
    return source.read_text()
""",
    )
    _write(
        root,
        "src/usage.py",
        """import threading
from pathlib import Path

STATE_LOCK = threading.Lock()

def save(path: Path, text: str):
    with STATE_LOCK:
        temporary = path.with_suffix('.tmp')
        temporary.write_text(text)
        temporary.replace(path)
""",
    )
    _write(
        root,
        "src/provider.py",
        """import json

def is_cloudflare_quota_error(error):
    message = str(error).lower()
    return bool(
        'http 429' in message
        or 'code 4006' in message
        or 'daily allocation is exhausted' in message
    )

def json_candidate_score(payload):
    return 10, len(json.dumps(payload))

def parse_json(objects):
    return max(objects, key=json_candidate_score)
""",
    )
    return [
        workflow,
        "docs/certification-assurance.md",
        test_path,
        "src/cloudflare_cli.py",
        "src/incremental.py",
        "src/scout.py",
        "src/usage.py",
        "src/provider.py",
    ]


def _clean_formation(root: Path) -> list[str]:
    workflow = ".github/workflows/certify.yml"
    test_path = "tests/test_certification_workflow_contract.py"
    model_rows = "\n".join(f"              '{model}'," for model in MODELS)
    _write(
        root,
        workflow,
        f"""name: certify
on:
  pull_request:
    paths:
      - '.github/workflows/certify.yml'
      - '{test_path}'
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: python -m pytest -q {test_path}
  certify:
    needs: validate
    if: ${{{{ vars.CERTIFICATION_ENABLED == 'true' }}}}
    environment: protected-certification
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: python -m approved.certification
        env:
          API_TOKEN: ${{{{ secrets.API_TOKEN }}}}
      - run: |
          python - <<'PY'
          required = {{
{model_rows}
          }}
          assert set(payload.get('certified_models', [])) == required
          PY
""",
    )
    _write(
        root,
        "docs/certification-assurance.md",
        f"""# Assurance

Assured path: `{workflow}`
Purpose, permissions, secrets, rollback and proof are reviewed.
Focused proof requires `{test_path}`.
""",
    )
    _write(
        root,
        test_path,
        "REQUIRED_MODELS = {\n" + "\n".join(f'    "{model}",' for model in MODELS) + "\n}\n",
    )
    _write(
        root,
        "src/cloudflare_cli.py",
        """import re

SECURITY_MARKERS = (re.compile(r'\\brce\\b'), re.compile(r'\\bauth(?:entication|orization)?\\b'))

def proof_contract_matches(payload):
    candidates = [payload]
    result = payload.get('result')
    if isinstance(result, dict):
        candidates.append(result)
    return candidates
""",
    )
    _write(
        root,
        "src/incremental.py",
        """import json

def stop(ledger, utc_day):
    ledger['budget_blocked'] = True
    ledger['budget_blocked_day'] = utc_day
    return json.dumps(ledger)
""",
    )
    _write(
        root,
        "src/scout.py",
        """from pathlib import Path

def load(root, file):
    root_path = Path(root).resolve()
    source = (root_path / file).resolve()
    source.relative_to(root_path)
    return source.read_text()
""",
    )
    _write(
        root,
        "src/usage.py",
        """import os
import threading

STATE_LOCK = threading.Lock()

def lock(path):
    return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
""",
    )
    _write(
        root,
        "src/provider.py",
        """import json

def is_cloudflare_quota_error(error):
    text = str(error).lower()
    return '4006' in text or 'daily allocation exhausted' in text

def is_http_rate_limit_error(error):
    return 'http 429' in str(error).lower()

def json_candidate_score(payload):
    return 10

def parse_json(objects):
    indexed = list(enumerate(objects))
    return max(indexed, key=lambda item: (json_candidate_score(item[1]), item[0]))[1]
""",
    )
    return [
        workflow,
        "docs/certification-assurance.md",
        test_path,
        "src/cloudflare_cli.py",
        "src/incremental.py",
        "src/scout.py",
        "src/usage.py",
        "src/provider.py",
    ]


EXPECTED_ROOTS = {
    "workflow-secret-boundary",
    "workflow-proof-contract",
    "certification-roster-contract",
    "instruction-echo-contract",
    "ambiguous-security-coverage",
    "stale-budget-lifecycle",
    "unsafe-file-access",
    "cross-process-state-race",
    "quota-error-classification",
    "structured-response-selection",
    "atomic-replace-durability",
}


def test_offline_permanent_officers_detect_all_recovery_roots(tmp_path: Path) -> None:
    changed = _defective_formation(tmp_path)

    result = run_offline_investigations(tmp_path, changed)

    assert result["finding_count"] == 11
    assert {item["root_cause"] for item in result["findings"]} == EXPECTED_ROOTS
    assert {item["officer"] for item in result["findings"]} == {"Engineer", "Medic", "Mechanic"}
    assert all(item["direct_evidence"] is True for item in result["findings"])
    assert all(item["evidence_ref"] and item["falsifiers_checked"] for item in result["findings"])


def test_clean_counterparts_do_not_create_offline_findings(tmp_path: Path) -> None:
    changed = _clean_formation(tmp_path)

    result = run_offline_investigations(tmp_path, changed)

    assert result["findings"] == []


def test_cloudflare_backed_review_workflow_is_not_treated_as_roster_certification(
    tmp_path: Path,
) -> None:
    workflow = ".github/workflows/review-intelligence-proof.yml"
    contract = "tests/test_certification_workflow_contract.py"
    _write(
        tmp_path,
        workflow,
        """name: Review Intelligence Proof
on:
  pull_request:
  workflow_dispatch:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest -q tests/test_review_intelligence.py
  configured-model-review:
    needs: validate
    if: ${{ github.event_name == 'workflow_dispatch' }}
    environment: protected-model-review
    runs-on: ubuntu-latest
    env:
      SERGEANT_CLOUDFLARE_ACCOUNT_ID: ${{ secrets.SERGEANT_CLOUDFLARE_ACCOUNT_ID }}
      SERGEANT_CLOUDFLARE_API_TOKEN: ${{ secrets.SERGEANT_CLOUDFLARE_API_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - run: python -m main_review.cli review .
""",
    )
    _write(
        tmp_path,
        contract,
        "REQUIRED_MODELS = {\n" + "\n".join(f'    "{model}",' for model in MODELS) + "\n}\n",
    )

    result = run_offline_investigations(tmp_path, [workflow, contract])

    assert not any(
        item["root_cause"] == "certification-roster-contract"
        for item in result["findings"]
    )


def test_investigator_does_not_treat_its_rule_literals_as_quota_behavior(tmp_path: Path) -> None:
    source = Path("main_review/offline_investigation.py").read_text(encoding="utf-8")
    _write(tmp_path, "main_review/offline_investigation.py", source)

    result = run_offline_investigations(tmp_path, ["main_review/offline_investigation.py"])

    assert not any(item["root_cause"] == "quota-error-classification" for item in result["findings"])


def _formation(
    root: Path,
    changed: list[str],
    *,
    diff: dict | None = None,
    cpl: dict | None = None,
) -> dict:
    return run_officer_council(
        root,
        changed,
        repository_review={"verdict": {"verdict": "PASS"}, "evidence": {"findings": []}},
        diff=diff or {"verdict": {"verdict": "PASS"}, "evidence": {"findings": []}},
        capabilities={"verdict": "PASS", "findings": []},
        intelligence={"verdict": "PASS", "promoted_findings": []},
        standard={"passed": True, "blockers": []},
        cpl=cpl or {"status": "disabled", "passes": [], "actionable_findings": []},
    )


def test_officer_council_is_complete_and_actionable_without_models(tmp_path: Path) -> None:
    changed = _defective_formation(tmp_path)

    result = _formation(tmp_path, changed)

    assert result["mode"] == "deterministic_officer_formation"
    assert result["models_required"] is False
    assert result["model_support_status"] == "disabled"
    assert result["complete"] is True
    assert result["verdict"] == "BLOCK"
    assert len(result["admitted_findings"]) == 10
    assert {report["officer"] for report in result["reports"]} == set(OFFICER_ORDER)
    assert all("evidence_refs" in report and "model_support_status" in report for report in result["reports"])
    assert result["reports"][5]["root_cause_groups"]
    assert result["reports"][6]["challenges"]
    assert result["reports"][8]["admission_ledger"]["admitted"]
    assert result["transactions"][-1]["recipient"] == "Sergeant"


def test_generic_high_risk_signal_routes_to_satisfied_assurance_not_verdict(tmp_path: Path) -> None:
    path = ".github/workflows/ci.yml"
    _write(tmp_path, path, "name: ci\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
    diff = normalize_diff_review(review_changed_files([path]), tmp_path, [path])

    result = _formation(tmp_path, [path], diff=diff)

    assert result["verdict"] == "PASS"
    assert result["admitted_findings"] == []
    assert result["advisory_findings"][0]["admission"] == "risk_trigger"
    assurance = result["required_assurances"][0]
    assert assurance["required_assurance"] == "deterministic_officer_coverage"
    assert assurance["status"] == "satisfied"
    assert assurance["gates_verdict"] is False


def test_unreadable_high_risk_change_is_an_explicit_assurance_gate(tmp_path: Path) -> None:
    path = ".github/workflows/deleted.yml"
    diff = normalize_diff_review(review_changed_files([path]), tmp_path, [path])

    result = _formation(tmp_path, [path], diff=diff)

    assert result["verdict"] == "NEEDS WORK"
    assert result["admitted_findings"] == []
    assert result["unresolved_assurances"][0]["required_assurance"] == "deterministic_officer_coverage"


def test_models_amplify_existing_officer_packets_instead_of_creating_them(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "def ok(): return True\n")
    model_finding = {
        "officer": "Engineer",
        "capability": "api_contract",
        "severity": "major",
        "message": "Model found a grounded contract mismatch.",
        "path": "src/app.py",
        "line_start": 1,
        "line_end": 1,
        "evidence_ref": "src/app.py:1",
        "evidence": "The return value conflicts with the supplied contract.",
        "root_cause": "model-contract-mismatch",
        "direct_evidence": True,
        "supporting_models": ["model-a", "model-b"],
    }
    cpl = {
        "status": "completed",
        "actionable_findings": [model_finding],
        "passes": [{"supported_officer": "Engineer", "model": "model-a", "verdict": "NEEDS WORK"}],
    }

    result = _formation(tmp_path, ["src/app.py"], cpl=cpl)

    assert len(result["reports"]) == 10
    engineer = next(report for report in result["reports"] if report["officer"] == "Engineer")
    assert engineer["model_support"]
    assert engineer["admitted_findings"][0]["root_cause"] == "model-contract-mismatch"
