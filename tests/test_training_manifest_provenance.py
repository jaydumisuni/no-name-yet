from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from main_review.training_manifest_provenance import (
    ProvenanceError,
    validate_training_manifest,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", message],
        check=True,
    )
    return _git(root, "rev-parse", "HEAD")


def _lineage(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "target"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Sergeant Test"],
        check=True,
    )
    (root / "src").mkdir()
    (root / "src" / "service.py").write_text("value = 'defective'\n", encoding="utf-8")
    (root / "src" / "contract.py").write_text("OWNER = 'service'\n", encoding="utf-8")
    defective = _commit(root, "defective")
    (root / "src" / "service.py").write_text("value = 'fixed'\n", encoding="utf-8")
    fixing = _commit(root, "fix")
    subprocess.run(["git", "-C", str(root), "checkout", "-q", defective], check=True)
    return root, defective, fixing


def _manifest(root: Path, defective: str, fixing: str) -> dict:
    return {
        "set_id": "fresh-set",
        "rules": {
            "classification": "untouched_transfer_validation",
            "provenance_contract": "sergeant.training-provenance.v1",
            "provenance_required": True,
            "reviewer_code_frozen_before_target_selection": "a" * 40,
        },
        "cases": [
            {
                "case_id": "fresh-a",
                "repository": "example/target",
                "source_pr": 12,
                "checkout_path": str(root),
                "defective_ref": defective,
                "fixing_ref": fixing,
                "changed_files": ["src/service.py"],
                "context_files": ["src/contract.py"],
            }
        ],
    }


def test_verified_fix_parent_lineage_is_accepted(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    result = validate_training_manifest(_manifest(root, defective, fixing))
    assert result["status"] == "verified"
    assert result["cases"][0]["changed_files"] == ["src/service.py"]
    assert result["cases"][0]["context_files"] == ["src/contract.py"]


def test_scored_file_not_changed_by_fix_is_rejected(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    manifest = _manifest(root, defective, fixing)
    manifest["cases"][0]["changed_files"] = ["src/contract.py"]
    with pytest.raises(ProvenanceError, match="does not modify scored paths"):
        validate_training_manifest(manifest)


def test_checkout_must_be_frozen_at_defective_ref(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", fixing], check=True)
    with pytest.raises(ProvenanceError, match="HEAD must equal defective_ref"):
        validate_training_manifest(_manifest(root, defective, fixing))


def test_context_file_must_exist_at_defective_ref(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    manifest = _manifest(root, defective, fixing)
    manifest["cases"][0]["context_files"] = ["src/missing.py"]
    with pytest.raises(ProvenanceError, match="context_files.*does not exist"):
        validate_training_manifest(manifest)


def test_source_lineage_is_required_when_pr_is_unknown(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    manifest = _manifest(root, defective, fixing)
    manifest["cases"][0]["source_pr"] = None
    with pytest.raises(ProvenanceError, match="source_pr.*source_lineage"):
        validate_training_manifest(manifest)
    manifest["cases"][0]["source_lineage"] = "maintainer-fix-commit"
    assert validate_training_manifest(manifest)["status"] == "verified"


def test_full_frozen_reviewer_sha_is_required(tmp_path: Path) -> None:
    root, defective, fixing = _lineage(tmp_path)
    manifest = _manifest(root, defective, fixing)
    manifest["rules"]["reviewer_code_frozen_before_target_selection"] = "short"
    with pytest.raises(ProvenanceError, match="full reviewer_code"):
        validate_training_manifest(manifest)


def test_fixing_ref_must_descend_from_defective_ref(tmp_path: Path) -> None:
    root, defective, _ = _lineage(tmp_path)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "--orphan", "other"], check=True)
    for child in root.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            for nested in child.rglob("*"):
                if nested.is_file():
                    nested.unlink()
        elif child.is_file():
            child.unlink()
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "service.py").write_text("unrelated = True\n", encoding="utf-8")
    unrelated = _commit(root, "unrelated")
    subprocess.run(["git", "-C", str(root), "checkout", "-q", defective], check=True)
    with pytest.raises(ProvenanceError, match="not a descendant"):
        validate_training_manifest(_manifest(root, defective, unrelated))
