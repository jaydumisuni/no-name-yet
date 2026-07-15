from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one marker in {relative}, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "main_review/cpl_council.py",
    '        re.compile(r"(?:sql\\s+injection|unparameteri[sz]ed\\s+quer|raw\\s+sql|query\\s+concatenation)", re.I),\n',
    '''        re.compile(\n            r"(?:sql\\s+injection|unparameteri[sz]ed\\s+quer|raw\\s+sql|query\\s+concatenation|"\n            r"(?:interpolat|format|concatenat)[^\\n]{0,80}sql\\s+quer|sql\\s+quer[^\\n]{0,80}without\\s+parameter)",\n            re.I,\n        ),\n''',
)
replace_once(
    "main_review/cpl_council.py",
    '        re.compile(r"(?:missing\\s+authorization|lacks?\\s+(?:an?\\s+)?authorization|privileged\\s+route.*without)", re.I),\n',
    '''        re.compile(\n            r"(?:missing\\s+authorization|lacks?\\s+(?:an?\\s+)?(?:visible\\s+)?authorization|"\n            r"privileged(?:\\s+\\w+){0,2}\\s+route.*without)",\n            re.I,\n        ),\n''',
)

path = ROOT / "tests" / "test_cpl_noise_governor.py"
text = path.read_text(encoding="utf-8")
insert = '''\n\ndef test_live_authorization_wording_confirms_existing_authorization_gap() -> None:\n    deterministic = {\n        "category": "security_taint",\n        "severity": "major",\n        "message": "Privileged route lacks a visible authorization guard.",\n        "evidence": "An admin route was detected without an authorization guard.",\n        "path": "src/admin_api.py",\n        "line_start": 4,\n        "line_end": 4,\n        "root_cause": "authorization-gap",\n    }\n    candidates = [\n        {\n            "category": "security",\n            "severity": "major",\n            "message": "Privileged route lacks a visible authorization guard",\n            "evidence": "app.delete('/admin/users/:id', delete_user)",\n            "evidence_verified": True,\n            "path": "src/admin_api.py",\n            "line_start": 4,\n            "line_end": 4,\n            "supporting_models": ["model-a"],\n        },\n        {\n            "category": "security_taint",\n            "severity": "major",\n            "message": "Privileged admin route defined without any authentication or authorization guard.",\n            "evidence": "app.delete('/admin/users/:id', delete_user)",\n            "evidence_verified": True,\n            "path": "src/admin_api.py",\n            "line_start": 4,\n            "line_end": 4,\n            "supporting_models": ["model-b"],\n        },\n    ]\n\n    result = reconcile_cpl_findings(\n        {"status": "completed", "verdict": "NEEDS WORK", "findings": candidates},\n        [deterministic],\n    )\n\n    assert len(result["confirmed_findings"]) == 2\n    assert result["actionable_findings"] == []\n    assert result["unconfirmed_findings"] == []\n    assert result["decision_verdict"] == "PASS"\n\n\ndef test_live_sql_interpolation_wording_confirms_existing_unsafe_data_flow() -> None:\n    deterministic = {\n        "category": "data_flow",\n        "severity": "major",\n        "message": "User-controlled input appears near a risky sink.",\n        "evidence": "Input and sink patterns were both detected in the changed file.",\n        "path": "src/api.py",\n        "line_start": 3,\n        "line_end": 3,\n        "root_cause": "unsafe-data-flow",\n    }\n    candidate = {\n        "category": "correctness",\n        "severity": "major",\n        "message": "User-controlled input directly interpolated into SQL query without parameterization",\n        "evidence": 'return db.query(f"SELECT * FROM users WHERE id = {user_id}")',\n        "evidence_verified": True,\n        "path": "src/api.py",\n        "line_start": 3,\n        "line_end": 3,\n        "supporting_models": ["model-b"],\n    }\n\n    result = reconcile_cpl_findings(\n        {"status": "completed", "verdict": "NEEDS WORK", "findings": [candidate]},\n        [deterministic],\n    )\n\n    assert len(result["confirmed_findings"]) == 1\n    assert result["actionable_findings"] == []\n    assert result["unconfirmed_findings"] == []\n    assert result["decision_verdict"] == "PASS"\n'''
marker = "\n\ndef test_same_family_findings_remain_separate_when_far_apart() -> None:\n"
if insert.strip() not in text:
    if text.count(marker) != 1:
        raise SystemExit("Expected live replay insertion marker once.")
    path.write_text(text.replace(marker, insert + marker, 1), encoding="utf-8")

# Construction guarantees.
council = (ROOT / "main_review" / "cpl_council.py").read_text(encoding="utf-8")
assert council.count("interpolat|format|concatenat") == 1
assert council.count("privileged(?:\\s+\\w+){0,2}\\s+route") == 1
tests = path.read_text(encoding="utf-8")
assert tests.count("test_live_authorization_wording_confirms_existing_authorization_gap") == 1
assert tests.count("test_live_sql_interpolation_wording_confirms_existing_unsafe_data_flow") == 1
print("Live replay root-cause patterns applied.")
