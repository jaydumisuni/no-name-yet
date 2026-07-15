from __future__ import annotations

from pathlib import Path

import main_review.cloudflare_cli as cloudflare_cli
from main_review.cpl_council import finding_key, finding_root_cause, findings_match
from main_review.cloudflare_gateway import CloudflareGatewaySettings
from main_review.llm_review import _merge_passes


MODEL_A = "@cf/qwen/qwen3-30b-a3b-fp8"
MODEL_B = "@cf/openai/gpt-oss-20b"


def _shell_finding(*, line: int, message: str, evidence: str) -> dict:
    return {
        "severity": "blocker",
        "category": "security",
        "path": "src/auth.py",
        "line_start": line,
        "line_end": line,
        "message": message,
        "evidence": evidence,
        "evidence_verified": True,
        "why_it_matters": "User input can execute arbitrary system commands.",
        "safer_alternative": "Use shell=False with an explicit argument list.",
    }


def test_shell_command_variants_share_one_root_cause_identity() -> None:
    first = _shell_finding(
        line=4,
        message="Direct shell command execution with user-provided input",
        evidence="return subprocess.run(command, shell=True)",
    )
    second = _shell_finding(
        line=5,
        message="Unrestricted execution of user-supplied shell commands",
        evidence="subprocess.run(command, shell=True)",
    )

    assert finding_root_cause(first) == "unsafe-shell-execution"
    assert findings_match(first, second) is True


def test_same_root_cause_far_apart_remains_separate() -> None:
    first = _shell_finding(line=4, message="Command injection", evidence="shell=True")
    second = _shell_finding(line=44, message="Command injection", evidence="shell=True")

    assert findings_match(first, second) is False


def test_pass_merger_combines_independent_model_support_for_same_defect() -> None:
    passes = [
        {
            "model": MODEL_A,
            "specialist": "generalist",
            "verdict": "BLOCK",
            "confidence": 0.9,
            "findings": [
                _shell_finding(
                    line=4,
                    message="Direct shell command execution with user-provided input",
                    evidence="return subprocess.run(command, shell=True)",
                )
            ],
        },
        {
            "model": MODEL_B,
            "specialist": "security",
            "verdict": "BLOCK",
            "confidence": 0.9,
            "findings": [
                _shell_finding(
                    line=5,
                    message="Unrestricted execution of user-supplied shell commands",
                    evidence="subprocess.run(command, shell=True)",
                )
            ],
        },
    ]

    findings, verdict, confidence = _merge_passes(passes)

    assert verdict == "BLOCK"
    assert confidence == 0.9
    assert len(findings) == 1
    assert set(findings[0]["supporting_models"]) == {MODEL_A, MODEL_B}


def _settings() -> CloudflareGatewaySettings:
    return CloudflareGatewaySettings(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret-token",
        models=(MODEL_A, MODEL_B),
    )


def test_expected_blocker_contract_certifies_independent_council(tmp_path: Path, monkeypatch) -> None:
    finding = _shell_finding(
        line=4,
        message="Direct shell command execution with user-provided input",
        evidence="return subprocess.run(command, shell=True)",
    )
    finding["supporting_models"] = [MODEL_A, MODEL_B]
    monkeypatch.setattr(
        cloudflare_cli,
        "run_cpl_review",
        lambda *args, **kwargs: {
            "status": "completed",
            "verdict": "BLOCK",
            "passes": [
                {"model": MODEL_A, "findings": [finding]},
                {"model": MODEL_B, "findings": [finding]},
            ],
            "errors": [],
            "council": {
                "true_model_independence": True,
                "complete": True,
                "final_gaps": [],
                "effective_findings": [finding],
            },
        },
    )

    result = cloudflare_cli.run_council_proof(
        _settings(),
        root=tmp_path,
        changed_files=["src/auth.py"],
        expected_verdict="BLOCK",
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=True",
        minimum_supporting_models=2,
    )

    assert result["passed"] is True
    assert result["verdict_matches"] is True
    assert result["expected_finding"]["passed"] is True
    assert result["expected_finding"]["matches"][0]["support_count"] == 2


def test_expected_contract_rejects_single_model_support(tmp_path: Path, monkeypatch) -> None:
    finding = _shell_finding(line=4, message="Command injection", evidence="shell=True")
    finding["supporting_models"] = [MODEL_A]
    monkeypatch.setattr(
        cloudflare_cli,
        "run_cpl_review",
        lambda *args, **kwargs: {
            "status": "completed",
            "verdict": "BLOCK",
            "passes": [{"model": MODEL_A}, {"model": MODEL_B}],
            "errors": [],
            "council": {
                "true_model_independence": True,
                "complete": True,
                "final_gaps": [],
                "effective_findings": [finding],
            },
        },
    )

    result = cloudflare_cli.run_council_proof(
        _settings(),
        root=tmp_path,
        changed_files=["src/auth.py"],
        expected_verdict="BLOCK",
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=True",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False
    assert result["expected_finding"]["passed"] is False


def test_subprocess_without_shell_is_not_classified_as_shell_injection() -> None:
    finding = _shell_finding(
        line=4,
        message="Subprocess environment inherits an unsafe PATH",
        evidence="subprocess.run([tool, '--version'], shell=False)",
    )
    finding["why_it_matters"] = "Executable resolution may select an unintended binary."

    assert finding_root_cause(finding) != "unsafe-shell-execution"


def test_adjacent_lines_match_across_fixed_bucket_boundaries() -> None:
    left = _shell_finding(line=10, message="Command injection", evidence="shell=True")
    right = _shell_finding(line=11, message="Shell command execution", evidence="shell=True")
    right["category"] = "correctness"

    assert findings_match(left, right) is True


def test_expected_contract_uses_verified_evidence_only() -> None:
    finding = _shell_finding(
        line=4,
        message="Unsafe command",
        evidence="subprocess.run(command, shell=True)",
    )
    finding["evidence_verified"] = False
    finding["supporting_models"] = [MODEL_A, MODEL_B]
    result = cloudflare_cli._expected_finding_result(
        [finding],
        [
            {"model": MODEL_A, "findings": [finding]},
            {"model": MODEL_B, "findings": [finding]},
        ],
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=true",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False


def test_expected_contract_ignores_claimed_models_without_matching_passes() -> None:
    finding = _shell_finding(line=4, message="Command injection", evidence="shell=True")
    finding["supporting_models"] = [MODEL_A, MODEL_B, "invented-model"]
    result = cloudflare_cli._expected_finding_result(
        [finding],
        [{"model": MODEL_A, "findings": [finding]}, {"model": MODEL_B, "findings": []}],
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=true",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False
    assert result["matches"][0]["supporting_models"] == [MODEL_A]



def test_remediation_text_does_not_define_root_cause() -> None:
    finding = _shell_finding(
        line=4,
        message="Subprocess environment inherits an unsafe PATH",
        evidence="subprocess.run([tool, '--version'], shell=False)",
    )
    finding["why_it_matters"] = "Executable resolution may select an unintended binary."
    finding["safer_alternative"] = "Keep shell=True disabled and use an absolute executable path."

    assert finding_root_cause(finding) != "unsafe-shell-execution"


def test_pass_merger_retains_strongest_severity_regardless_of_order() -> None:
    major = _shell_finding(line=4, message="Command injection risk", evidence="shell=True")
    major["severity"] = "major"
    blocker = _shell_finding(line=5, message="Arbitrary shell command execution", evidence="shell=True")
    blocker["severity"] = "blocker"

    for ordered in ((major, blocker), (blocker, major)):
        findings, verdict, _ = _merge_passes([
            {
                "model": MODEL_A,
                "specialist": "generalist",
                "verdict": "NEEDS WORK",
                "confidence": 0.9,
                "findings": [ordered[0]],
            },
            {
                "model": MODEL_B,
                "specialist": "security",
                "verdict": "BLOCK",
                "confidence": 0.9,
                "findings": [ordered[1]],
            },
        ])

        assert len(findings) == 1
        assert findings[0]["severity"] == "blocker"
        assert verdict == "BLOCK"


def test_expected_support_requires_each_model_to_meet_full_contract() -> None:
    blocker = _shell_finding(line=4, message="Command injection", evidence="shell=True")
    weaker = _shell_finding(line=5, message="Shell execution concern", evidence="shell=True")
    weaker["severity"] = "minor"
    result = cloudflare_cli._expected_finding_result(
        [blocker],
        [
            {"model": MODEL_A, "findings": [blocker]},
            {"model": MODEL_B, "findings": [weaker]},
        ],
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=true",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False
    assert result["matches"][0]["supporting_models"] == [MODEL_A]
