from __future__ import annotations

from pathlib import Path

import main_review.cloudflare_incremental_certification as incremental
from main_review.capability_policy import normalize_capability_review
from main_review.cloudflare_cli import _coverage_area_matches
from main_review.officer_council import run_officer_council
from main_review.offline_investigation import run_offline_investigations
from main_review.review_benchmark import extract_predictions
from main_review.squad import build_squad_reports


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_permanent_officers_detect_six_new_static_root_classes(tmp_path: Path) -> None:
    files = {
        ".github/workflows/restore.yml": """name: restore
on: workflow_dispatch
jobs:
  restore:
    runs-on: ubuntu-latest
    steps:
      - run: artifact_id="$(${GH_TOKEN:+gh api /artifacts 2>/dev/null || true})"
""",
        "src/ledger.py": """import tempfile

def save_ledger(path, payload):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
        handle.write(payload)
        temporary = path.__class__(handle.name)
    temporary.replace(path)
""",
        "src/council.py": """def normalize(item):
    finding = dict(item)
    finding['severity'] = finding.get('severity')
    return finding

def status(item):
    return item.get('severity') in {'blocker', 'major'}

def transactions(admitted, advisory, rejected):
    disposition = {
        **{item['finding_id']: 'admitted' for item in admitted},
        **{item['finding_id']: 'advisory' for item in advisory},
        **{item['finding_id']: 'rejected' for item in rejected},
    }
    return disposition
""",
        "src/benchmark.py": """def predictions(formation):
    return [
        item for item in formation.get('advisory_findings', [])
        if item.get('admission') in {'advisory', 'risk_trigger'}
    ]
""",
        "src/squad.py": """def build_reports(formation_reports, learning, graduation):
    if formation_reports:
        return list(formation_reports)
    return [{'learning': learning, 'graduation': graduation}]
""",
    }
    for path, content in files.items():
        _write(tmp_path, path, content)

    result = run_offline_investigations(tmp_path, list(files))

    assert {item["root_cause"] for item in result["findings"]} == {
        "workflow-shell-operator-expansion",
        "atomic-replace-durability",
        "severity-canonicalization",
        "disposition-precedence",
        "benchmark-risk-trigger-filter",
        "formation-evidence-loss",
    }


def test_clean_static_counterparts_do_not_create_findings(tmp_path: Path) -> None:
    files = {
        ".github/workflows/restore.yml": """name: restore
on: workflow_dispatch
jobs:
  restore:
    runs-on: ubuntu-latest
    steps:
      - run: |
          artifact_id=""
          if [ -n "${GH_TOKEN:-}" ]; then
            artifact_id="$(gh api /artifacts 2>/dev/null || true)"
          fi
""",
        "src/ledger.py": """import os
import tempfile

def save_ledger(path, payload):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = path.__class__(handle.name)
    temporary.replace(path)
""",
        "src/council.py": """def normalize(item):
    finding = dict(item)
    finding['severity'] = str(finding.get('severity') or 'unknown').lower()
    return finding

def status(item):
    return item.get('severity') in {'blocker', 'major'}

def transactions(admitted, advisory, rejected):
    disposition = {item['finding_id']: 'rejected' for item in rejected}
    disposition.update({item['finding_id']: 'advisory' for item in advisory})
    disposition.update({item['finding_id']: 'admitted' for item in admitted})
    return disposition
""",
        "src/benchmark.py": """def predictions(formation):
    return [
        item for item in formation.get('advisory_findings', [])
        if item.get('admission') == 'advisory'
    ]
""",
        "src/squad.py": """def build_reports(formation_reports, learning, graduation):
    if formation_reports:
        reports = list(formation_reports)
        reports.append({'learning': learning, 'graduation': graduation})
        return reports
    return []
""",
    }
    for path, content in files.items():
        _write(tmp_path, path, content)

    result = run_offline_investigations(tmp_path, list(files))

    assert result["findings"] == []


def test_incremental_ledger_flushes_and_fsyncs_before_replace(tmp_path: Path, monkeypatch) -> None:
    operations: list[str] = []
    original_named_temporary_file = incremental.tempfile.NamedTemporaryFile
    original_replace = incremental.Path.replace

    def tracked_named_temporary_file(*args, **kwargs):
        handle = original_named_temporary_file(*args, **kwargs)
        original_flush = handle.flush

        def tracked_flush():
            operations.append("flush")
            return original_flush()

        handle.flush = tracked_flush
        return handle

    def tracked_fsync(descriptor: int) -> None:
        operations.append("fsync")

    def tracked_replace(source: Path, destination: Path) -> Path:
        operations.append("replace")
        return original_replace(source, destination)

    monkeypatch.setattr(incremental.tempfile, "NamedTemporaryFile", tracked_named_temporary_file)
    monkeypatch.setattr(incremental.os, "fsync", tracked_fsync)
    monkeypatch.setattr(incremental.Path, "replace", tracked_replace)
    path = tmp_path / "ledger.json"

    incremental.save_ledger(path, incremental._fresh_ledger("head-sha"))

    assert operations == ["flush", "fsync", "replace"]
    assert incremental.load_ledger(path, "head-sha")["tested_sha"] == "head-sha"


def test_review_intelligence_model_identifier_is_non_secret_configuration() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/review-intelligence-proof.yml"
    ).read_text(encoding="utf-8")

    assert "SERGEANT_CPL_MODEL: ${{ vars.SERGEANT_CPL_MODEL }}" in workflow
    assert "SERGEANT_CPL_MODEL: ${{ secrets.SERGEANT_CPL_MODEL }}" not in workflow


def test_multiline_workflow_detects_python_runner_after_setup_command(tmp_path: Path) -> None:
    workflow = ".github/workflows/proof.yml"
    test_path = "tests/test_required.py"
    _write(tmp_path, "docs/proof.md", f"Assured workflow `{workflow}` must run `{test_path}`.\n")
    _write(
        tmp_path,
        workflow,
        f"""on:
  pull_request:
    paths: ['{test_path}']
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: |
          python -m pip install -e .
          python -m pytest {test_path}
""",
    )

    result = run_offline_investigations(tmp_path, ["docs/proof.md", workflow])

    assert not any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_workflow_shell_expansion_ignores_comments_and_inert_values(tmp_path: Path) -> None:
    workflow = ".github/workflows/inert.yml"
    _write(
        tmp_path,
        workflow,
        """on: workflow_dispatch
env:
  DOCUMENTATION_EXAMPLE: '${TOKEN:+command || true}'
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      # ${TOKEN:+command || true}
      - run: echo safe
""",
    )

    result = run_offline_investigations(tmp_path, [workflow])

    assert not any(item["root_cause"] == "workflow-shell-operator-expansion" for item in result["findings"])


def test_workflow_contract_associates_each_test_with_its_workflow(tmp_path: Path) -> None:
    workflow_a = ".github/workflows/a.yml"
    workflow_b = ".github/workflows/b.yml"
    test_a = "tests/test_a.py"
    test_b = "tests/test_b.py"
    _write(
        tmp_path,
        "docs/proof.md",
        f"`{workflow_a}` assures `{test_a}`.\n`{workflow_b}` assures `{test_b}`.\n",
    )
    for workflow, test_path in ((workflow_a, test_a), (workflow_b, test_b)):
        _write(
            tmp_path,
            workflow,
            f"""on:
  pull_request:
    paths: ['{test_path}']
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest {test_path}
""",
        )

    result = run_offline_investigations(
        tmp_path,
        ["docs/proof.md", workflow_a, workflow_b, test_a, test_b],
    )

    assert not any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_atomic_replace_requires_flush_and_fsync_before_replace(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/ledger.py",
        """import os
import tempfile

def save_ledger(path, payload):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
        handle.write(payload)
        temporary = path.__class__(handle.name)
    temporary.replace(path)
    handle.flush()
    os.fsync(handle.fileno())
""",
    )

    result = run_offline_investigations(tmp_path, ["src/ledger.py"])

    assert any(item["root_cause"] == "atomic-replace-durability" for item in result["findings"])


def test_python_methods_and_async_functions_are_fully_investigated(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/service.py",
        """import tempfile

class Store:
    def save_ledger(self, path, payload):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
            handle.write(payload)
            temporary = path.__class__(handle.name)
        temporary.replace(path)

async def normalize_finding(item):
    finding = dict(item)
    finding['severity'] = finding.get('severity')
    return finding

def status(item):
    return item.get('severity') in {'blocker', 'major'}
""",
    )

    result = run_offline_investigations(tmp_path, ["src/service.py"])
    roots = {item["root_cause"] for item in result["findings"]}

    assert {"atomic-replace-durability", "severity-canonicalization"} <= roots


def test_all_candidate_functions_are_checked_after_clean_predecessors(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/council.py",
        """def normalize_good(item):
    finding = dict(item)
    finding['severity'] = str(finding.get('severity') or 'unknown').lower()
    return finding

def normalize_bad(item):
    finding = dict(item)
    finding['severity'] = finding.get('severity')
    return finding

def status(item):
    return item.get('severity') in {'blocker', 'major'}

def build_good_reports(formation_reports, learning, graduation):
    if formation_reports:
        reports = list(formation_reports)
        reports.append({'learning': learning, 'graduation': graduation})
        return reports
    return []

def build_bad_reports(formation_reports, learning, graduation):
    if formation_reports:
        return list(formation_reports)
    return [{'learning': learning, 'graduation': graduation}]
""",
    )

    result = run_offline_investigations(tmp_path, ["src/council.py"])
    roots = {item["root_cause"] for item in result["findings"]}

    assert {"severity-canonicalization", "formation-evidence-loss"} <= roots


def test_capability_policy_canonicalizes_uppercase_blocker(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "VALUE = 1\n")
    packet = normalize_capability_review(
        {
            "verdict": "PASS",
            "changed_files": ["src/app.py"],
            "findings": [
                {
                    "capability": "test_impact",
                    "severity": "BLOCKER",
                    "path": "src/app.py",
                    "line_start": 1,
                    "message": "Grounded security defect.",
                    "evidence": "Direct changed-line evidence.",
                }
            ],
        },
        tmp_path,
    )

    assert packet["findings"][0]["severity"] == "blocker"
    assert packet["verdict"] == "BLOCK"


def test_uppercase_blocker_controls_verdict_and_duplicate_keeps_admitted_precedence(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "VALUE = 1\n")
    finding = {
        "officer": "Engineer",
        "capability": "api_contract",
        "severity": "BLOCKER",
        "message": "Grounded contract failure.",
        "path": "src/app.py",
        "line_start": 1,
        "root_cause": "uppercase-contract",
        "direct_evidence": True,
        "evidence_ref": "src/app.py:1",
    }
    result = run_officer_council(
        tmp_path,
        ["src/app.py"],
        repository_review={"verdict": {"verdict": "PASS"}, "evidence": {"findings": [finding]}},
        diff={"verdict": {"verdict": "PASS"}, "evidence": {"findings": []}},
        capabilities={"verdict": "PASS", "findings": []},
        intelligence={"verdict": "PASS", "promoted_findings": []},
        standard={"passed": True, "blockers": []},
        cpl={"status": "completed", "passes": [], "actionable_findings": [finding]},
    )

    assert result["verdict"] == "BLOCK"
    assert result["admitted_findings"][0]["severity"] == "blocker"
    assert result["required_actions"]
    judge = next(report for report in result["reports"] if report["officer"] == "Judge")
    ledger = judge["admission_ledger"]
    assert set(ledger["admitted"]).isdisjoint(ledger["rejected"])
    finding_id = result["admitted_findings"][0]["finding_id"]
    disposition = next(
        item["disposition"]
        for item in result["transactions"]
        if item.get("transaction") == "claim_adjudicated" and item.get("finding_id") == finding_id
    )
    assert disposition == "admitted"


def test_default_checkout_requires_pull_request_trigger_before_secret_boundary_blocks(tmp_path: Path) -> None:
    common_job = """jobs:
  live:
    runs-on: ubuntu-latest
    env:
      TOKEN: ${{ secrets.TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install -e .
"""
    _write(tmp_path, ".github/workflows/push.yml", "on: push\n" + common_job)
    _write(tmp_path, ".github/workflows/pr.yml", "on: pull_request\n" + common_job)

    push = run_offline_investigations(tmp_path, [".github/workflows/push.yml"])
    pull_request = run_offline_investigations(tmp_path, [".github/workflows/pr.yml"])

    assert not any(item["root_cause"] == "workflow-secret-boundary" for item in push["findings"])
    assert any(item["root_cause"] == "workflow-secret-boundary" for item in pull_request["findings"])


def test_workflow_proof_requires_real_trigger_and_executed_command(tmp_path: Path) -> None:
    workflow = ".github/workflows/proof.yml"
    test_path = "tests/test_required.py"
    _write(
        tmp_path,
        "docs/proof.md",
        f"Assured workflow `{workflow}` must run `{test_path}`.\n",
    )
    _write(
        tmp_path,
        workflow,
        f"""on:
  push:
    paths: [src/**]
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      # {test_path}
      # {test_path}
      - run: pytest tests/test_other.py
""",
    )
    bad = run_offline_investigations(tmp_path, ["docs/proof.md", workflow])
    assert any(item["root_cause"] == "workflow-proof-contract" for item in bad["findings"])

    _write(
        tmp_path,
        workflow,
        f"""on:
  pull_request:
    paths:
      - '{test_path}'
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: pytest {test_path}
""",
    )
    clean = run_offline_investigations(tmp_path, ["docs/proof.md", workflow])
    assert not any(item["root_cause"] == "workflow-proof-contract" for item in clean["findings"])


def test_workflow_proof_does_not_treat_echoed_test_path_as_execution(tmp_path: Path) -> None:
    workflow = ".github/workflows/proof.yml"
    test_path = "tests/test_required.py"
    _write(tmp_path, "docs/proof.md", f"Assured workflow `{workflow}` must run `{test_path}`.\n")
    _write(
        tmp_path,
        workflow,
        f"""on:
  pull_request:
    paths: ['{test_path}']
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: echo pytest {test_path}
""",
    )

    result = run_offline_investigations(tmp_path, ["docs/proof.md", workflow])

    assert any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_single_quoted_security_marker_keeps_grounded_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/security.py",
        "def covered(area):\n    SECURITY_MARKERS = ('rce', 'auth')\n    return any(marker in area for marker in SECURITY_MARKERS)\n",
    )

    result = run_offline_investigations(tmp_path, ["src/security.py"])
    finding = next(item for item in result["findings"] if item["root_cause"] == "ambiguous-security-coverage")

    assert finding["line_start"] == 2
    assert finding["evidence_ref"] == "src/security.py:2"


def test_readable_empty_file_is_not_an_unavailable_assurance_gap(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/empty.yml", "")

    result = run_offline_investigations(tmp_path, [".github/workflows/empty.yml"])

    assert result["readable_changed_files"] == [".github/workflows/empty.yml"]
    assert result["unavailable_changed_files"] == []


def test_benchmark_excludes_every_risk_trigger_but_keeps_true_advisory() -> None:
    risk = {
        "officer_council": {
            "admitted_findings": [],
            "advisory_findings": [
                {
                    "severity": "minor",
                    "admission": "risk_trigger",
                    "message": "Any novel routing signal.",
                    "path": "src/app.py",
                }
            ],
        }
    }
    predictions, count = extract_predictions(risk)
    assert predictions == []
    assert count == 0

    risk["officer_council"]["advisory_findings"][0]["admission"] = "advisory"
    predictions, count = extract_predictions(risk)
    assert len(predictions) == count == 1


def test_impact_context_does_not_demote_a_real_advisory_to_risk_trigger(tmp_path: Path) -> None:
    _write(tmp_path, "src/api.py", "def route(): return True\n")
    advisory = {
        "officer": "Engineer",
        "capability": "api_contract",
        "severity": "minor",
        "message": "API route contract changed or requires compatibility review.",
        "path": "src/api.py",
        "line_start": 1,
        "root_cause": "change-impact",
        "impact_signal": True,
    }
    result = run_officer_council(
        tmp_path,
        ["src/api.py"],
        repository_review={"verdict": {"verdict": "PASS"}, "evidence": {"findings": [advisory]}},
        diff={"verdict": {"verdict": "PASS"}, "evidence": {"findings": []}},
        capabilities={"verdict": "PASS", "findings": []},
        intelligence={"verdict": "PASS", "promoted_findings": []},
        standard={"passed": True, "blockers": []},
        cpl={"status": "disabled", "passes": [], "actionable_findings": []},
    )

    assert result["advisory_findings"][0]["admission"] == "advisory"


def test_canonical_formation_enriches_archivist_and_judge() -> None:
    packet = {
        "officer_council": {
            "reports": [
                {"agent": "archivist", "officer": "Archivist", "findings": []},
                {"agent": "judge", "officer": "Judge", "findings": []},
            ]
        }
    }
    learning = {"learning": {"candidates": [{"id": "verified-memory"}]}}
    graduation = {"verdict": "GRADUATED", "delta": 0.2}

    reports = build_squad_reports(packet, {}, learning, graduation)
    archivist, judge = reports

    assert archivist["learning_candidates"] == [{"id": "verified-memory"}]
    assert archivist["findings"] == [{"id": "verified-memory"}]
    assert judge["graduation"] == graduation
    assert judge["findings"] == [{"verdict": "GRADUATED", "delta": 0.2}]


def test_coverage_helper_is_defensively_case_insensitive() -> None:
    assert _coverage_area_matches("security", {"Security"}) is True
    assert _coverage_area_matches("SECURITY", {"Injection"}) is True


def test_empty_workflow_still_fails_documented_proof_contract(tmp_path: Path) -> None:
    workflow = ".github/workflows/empty.yml"
    test_path = "tests/test_required.py"
    _write(tmp_path, "docs/proof.md", f"`{workflow}` assures `{test_path}`.\n")
    _write(tmp_path, workflow, "")
    _write(tmp_path, test_path, "def test_required():\n    assert True\n")
    result = run_offline_investigations(tmp_path, ["docs/proof.md", workflow, test_path])
    assert any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_runner_path_must_be_in_runner_invocation_not_comment_or_echo(tmp_path: Path) -> None:
    workflow = ".github/workflows/tests.yml"
    required = "tests/test_required.py"
    other = "tests/test_other.py"
    _write(tmp_path, "docs/proof.md", f"`{workflow}` assures `{required}`.\n")
    _write(tmp_path, workflow, f"""on:
  pull_request:
    paths: ['{required}']
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: |
          echo {required}
          # pytest {required}
          python -m pytest {other}
""")
    _write(tmp_path, required, "def test_required():\n    assert True\n")
    _write(tmp_path, other, "def test_other():\n    assert True\n")
    result = run_offline_investigations(tmp_path, ["docs/proof.md", workflow, required, other])
    assert any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_folded_run_scalar_does_not_create_fake_runner_command(tmp_path: Path) -> None:
    workflow = ".github/workflows/folded.yml"
    required = "tests/test_required.py"
    _write(tmp_path, "docs/proof.md", f"`{workflow}` assures `{required}`.\n")
    _write(tmp_path, workflow, f"""on:
  pull_request:
    paths: ['{required}']
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: >
          echo preparing
          pytest {required}
""")
    _write(tmp_path, required, "def test_required():\n    assert True\n")
    result = run_offline_investigations(tmp_path, ["docs/proof.md", workflow, required])
    assert any(item["root_cause"] == "workflow-proof-contract" for item in result["findings"])


def test_every_atomic_replacement_requires_its_own_durability_chain(tmp_path: Path) -> None:
    _write(tmp_path, "src/two_ledgers.py", """import os
import tempfile

def save(a, b, first, second):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as one:
        one.write(first)
        one.flush()
        os.fsync(one.fileno())
        one_path = a.__class__(one.name)
    one_path.replace(a)
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as two:
        two.write(second)
        two_path = b.__class__(two.name)
    two_path.replace(b)
""")
    result = run_offline_investigations(tmp_path, ["src/two_ledgers.py"])
    assert any(item["root_cause"] == "atomic-replace-durability" for item in result["findings"])


def test_multiple_atomic_replacements_pass_when_each_is_durable(tmp_path: Path) -> None:
    _write(tmp_path, "src/two_ledgers.py", """import os
import tempfile

def save(a, b, first, second):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as one:
        one.write(first)
        one.flush()
        os.fsync(one.fileno())
        one_path = a.__class__(one.name)
    one_path.replace(a)
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as two:
        two.write(second)
        two.flush()
        os.fsync(two.fileno())
        two_path = b.__class__(two.name)
    two_path.replace(b)
""")
    result = run_offline_investigations(tmp_path, ["src/two_ledgers.py"])
    assert not any(item["root_cause"] == "atomic-replace-durability" for item in result["findings"])


def test_string_replace_is_not_treated_as_atomic_file_publication(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/text.py",
        """def normalize(value):
    return value.replace('old', 'new')
""",
    )

    result = run_offline_investigations(tmp_path, ["src/text.py"])

    assert not any(item["root_cause"] == "atomic-replace-durability" for item in result["findings"])


def test_each_publication_requires_a_fresh_durability_sequence(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/ledger.py",
        """import os
import tempfile


def publish_twice(first, second, payload):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = first.__class__(handle.name)
    temporary.replace(first)
    temporary.replace(second)
""",
    )

    result = run_offline_investigations(tmp_path, ["src/ledger.py"])

    findings = [item for item in result["findings"] if item["root_cause"] == "atomic-replace-durability"]
    assert len(findings) == 1
    assert "temporary" in findings[0]["evidence"]


def test_independent_temporary_publications_each_with_own_sequence_are_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/ledger.py",
        """import os
import tempfile


def publish_two(first, second, payload):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as first_handle:
        first_handle.write(payload)
        first_handle.flush()
        os.fsync(first_handle.fileno())
        first_temp = first.__class__(first_handle.name)
    first_temp.replace(first)
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as second_handle:
        second_handle.write(payload)
        second_handle.flush()
        os.fsync(second_handle.fileno())
        second_temp = second.__class__(second_handle.name)
    second_temp.replace(second)
""",
    )

    result = run_offline_investigations(tmp_path, ["src/ledger.py"])

    assert not any(item["root_cause"] == "atomic-replace-durability" for item in result["findings"])
