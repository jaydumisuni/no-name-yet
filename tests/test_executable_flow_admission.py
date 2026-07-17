from __future__ import annotations

from pathlib import Path

from main_review.capability_policy import normalize_capability_review
from main_review.officer_council import _adjudicate, _normalize


def _normalized_candidates(tmp_path: Path, source_name: str, source_text: str):
    source = tmp_path / source_name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    packet = normalize_capability_review(
        {
            "verdict": "NEEDS WORK",
            "changed_files": [source_name],
            "findings": [
                {
                    "capability": capability,
                    "severity": "major",
                    "path": source_name,
                    "message": message,
                    "evidence": "Input and a sensitive sink were detected in changed source.",
                }
                for capability, message in (
                    ("data_flow", "User-controlled input appears near a risky sink."),
                    ("security_taint", "Potential tainted input path needs validation review."),
                )
            ],
        },
        tmp_path,
    )
    return [_normalize(item, "capability") for item in packet["findings"]]


def test_typescript_assignment_flow_to_exec_is_actionable(tmp_path: Path) -> None:
    candidates = _normalized_candidates(
        tmp_path,
        "src/jobs.ts",
        """import { exec } from 'node:child_process';
export function runJob(req: { body: { command: string } }) {
  const command = req.body.command;
  return exec(command);
}
""",
    )

    admitted, advisory, rejected = _adjudicate(candidates, {"promoted_findings": []})

    assert len(admitted) == 2
    assert advisory == []
    assert rejected == []
    assert all(item.get("executable_flow_proof") is True for item in admitted)


def test_go_assignment_flow_to_query_is_actionable(tmp_path: Path) -> None:
    candidates = _normalized_candidates(
        tmp_path,
        "internal/users.go",
        """package internal
func UserByID(db *DB, r *Request) error {
  id := r.URL.Query().Get("id")
  return db.Query("SELECT * FROM users WHERE id = " + id)
}
""",
    )

    admitted, advisory, rejected = _adjudicate(candidates, {"promoted_findings": []})

    assert len(admitted) == 2
    assert advisory == []
    assert rejected == []
    assert all(item.get("executable_flow_proof") is True for item in admitted)


def test_unrelated_typescript_functions_remain_advisory(tmp_path: Path) -> None:
    candidates = _normalized_candidates(
        tmp_path,
        "src/jobs.ts",
        """import { exec } from 'node:child_process';
export function parseJob(req: { body: { command: string } }) {
  return req.body.command;
}
export function runFixedJob() {
  return exec('echo safe');
}
""",
    )

    admitted, advisory, rejected = _adjudicate(candidates, {"promoted_findings": []})

    assert admitted == []
    assert rejected == []
    assert len(advisory) == 2
    assert all(not item.get("executable_flow_proof") for item in advisory)
