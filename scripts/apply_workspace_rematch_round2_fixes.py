from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {relative}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "main_review/offline_investigation.py",
    """        if inline and inline not in literal_markers | folded_markers:\n            command_lines.append(inline)\n""",
    """        if inline and inline not in literal_markers | folded_markers:\n            command_lines.append(_clean_yaml_scalar(inline))\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """def _executed_test_paths(text: str) -> set[str]:\n    \"\"\"Return test paths appearing in actual runner invocations only.\"\"\"\n""",
    """def _strip_shell_comment(command: str) -> str:\n    \"\"\"Remove an unquoted shell comment without changing quoted hashes.\"\"\"\n\n    quote: str | None = None\n    escaped = False\n    for index, character in enumerate(command):\n        if escaped:\n            escaped = False\n            continue\n        if character == \"\\\\\" and quote != \"'\":\n            escaped = True\n            continue\n        if character in {\"'\", '\"'}:\n            if quote is None:\n                quote = character\n            elif quote == character:\n                quote = None\n            continue\n        if character == \"#\" and quote is None and (index == 0 or command[index - 1].isspace()):\n            return command[:index].rstrip()\n    return command\n\n\ndef _executed_test_paths(text: str) -> set[str]:\n    \"\"\"Return test paths appearing in actual runner invocations only.\"\"\"\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        for logical in logical_lines:\n            for segment in re.split(r\"\\s*(?:&&|\\|\\||;|\\|)\\s*\", logical):\n""",
    """        for logical in logical_lines:\n            logical = _strip_shell_comment(logical)\n            if not logical:\n                continue\n            for segment in re.split(r\"\\s*(?:&&|\\|\\||;|\\|)\\s*\", logical):\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        for match in re.finditer(r\"\\b([A-Za-z_][A-Za-z0-9_]*)\\.replace\\s*\\(\", body):\n            replacements.append((match.start(), match.group(1)))\n""",
    """        known_path_receivers = set(aliases) | set(fd_paths)\n        for match in re.finditer(r\"\\b([A-Za-z_][A-Za-z0-9_]*)\\.replace\\s*\\(\", body):\n            receiver = match.group(1)\n            if receiver in known_path_receivers:\n                replacements.append((match.start(), receiver))\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        non_durable: list[str] = []\n        for replace_pos, source in sorted(replacements):\n""",
    """        non_durable: list[str] = []\n        publication_boundaries: dict[str, int] = {}\n        for replace_pos, source in sorted(replacements):\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """                durable = any(\n                    write < flush < fsync < replace_pos\n                    for write in write_positions\n                    for flush in flush_positions\n                    for fsync in fsync_positions\n                )\n""",
    """                identity = f\"handle:{handle}\"\n                lower_bound = publication_boundaries.get(identity, -1)\n                durable = any(\n                    lower_bound < write < flush < fsync < replace_pos\n                    for write in write_positions\n                    for flush in flush_positions\n                    for fsync in fsync_positions\n                )\n                if durable:\n                    publication_boundaries[identity] = replace_pos\n""",
)

replace_once(
    "main_review/offline_investigation.py",
    """                durable = any(write < fsync < replace_pos for write in writes for fsync in fsyncs)\n""",
    """                identity = f\"fd:{fd}\"\n                lower_bound = publication_boundaries.get(identity, -1)\n                durable = any(lower_bound < write < fsync < replace_pos for write in writes for fsync in fsyncs)\n                if durable:\n                    publication_boundaries[identity] = replace_pos\n""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """def _validate_adapter_evidence(\n    result: dict[str, Any],\n    task: dict[str, Any],\n    *,\n    adapter_name: str,\n    research: bool,\n) -> dict[str, Any] | None:\n""",
    """def _validate_adapter_evidence(\n    result: dict[str, Any],\n    task: dict[str, Any],\n    *,\n    request: dict[str, Any],\n    adapter_name: str,\n    research: bool,\n) -> dict[str, Any] | None:\n""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """    if provenance.get(\"adapter\") != adapter_name:\n        raise ValueError(\"adapter evidence provenance does not match the executing adapter\")\n    return validate_evidence_packet(packet, task)\n""",
    """    if provenance.get(\"adapter\") != adapter_name:\n        raise ValueError(\"adapter evidence provenance does not match the executing adapter\")\n    if research:\n        allowed_sources = {str(item) for item in request.get(\"allowed_sources\", []) if str(item)}\n        if str(provenance.get(\"source\")) not in allowed_sources:\n            raise ValueError(\"research evidence source is outside the authorized source policy\")\n    return validate_evidence_packet(packet, task)\n""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """            packet = _validate_adapter_evidence(result, task, adapter_name=workspace.name, research=False)\n""",
    """            packet = _validate_adapter_evidence(\n                result, task, request=request, adapter_name=workspace.name, research=False\n            )\n""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """            packet = _validate_adapter_evidence(result, task, adapter_name=research.name, research=True)\n""",
    """            packet = _validate_adapter_evidence(\n                result, task, request=request, adapter_name=research.name, research=True\n            )\n""",
)

TEST = ROOT / "tests/test_workspace_rematch_round2.py"
TEST.write_text(
    '''from __future__ import annotations

from main_review.offline_investigation import (
    _atomic_replace_without_fsync,
    _executed_test_paths,
)
from main_review.operational_contracts import evidence_packet, research_request, task_packet
from main_review.workspace_interfaces import dispatch_authorized_requests


def test_quoted_inline_workflow_command_is_decoded() -> None:
    workflow = 'steps:\n  - run: "pytest tests/test_required.py"\n'
    assert _executed_test_paths(workflow) == {"tests/test_required.py"}


def test_inline_shell_comment_cannot_invent_executed_test_path() -> None:
    workflow = "steps:\n  - run: pytest tests/other.py # tests/test_required.py\n"
    assert _executed_test_paths(workflow) == {"tests/other.py"}


def test_string_replace_is_not_treated_as_atomic_file_publication() -> None:
    source = '''\ndef normalize(value: str) -> str:\n    return value.replace("old", "new")\n'''
    assert _atomic_replace_without_fsync("main_review/example.py", source) == []


def test_one_durability_sequence_cannot_satisfy_two_publications() -> None:
    source = '''\ndef publish_twice(first, second):\n    with NamedTemporaryFile(mode="w", delete=False) as handle:\n        handle.write("payload")\n        handle.flush()\n        os.fsync(handle.fileno())\n        temp_path = handle.name\n    os.replace(temp_path, first)\n    os.replace(temp_path, second)\n'''
    findings = _atomic_replace_without_fsync("main_review/example.py", source)
    assert len(findings) == 1
    assert "temp_path" in findings[0].evidence


def test_separate_durable_handles_can_be_published_after_preparation() -> None:
    source = '''\ndef publish_two(first, second):\n    with NamedTemporaryFile(mode="w", delete=False) as first_handle:\n        first_handle.write("first")\n        first_handle.flush()\n        os.fsync(first_handle.fileno())\n        first_path = first_handle.name\n    with NamedTemporaryFile(mode="w", delete=False) as second_handle:\n        second_handle.write("second")\n        second_handle.flush()\n        os.fsync(second_handle.fileno())\n        second_path = second_handle.name\n    os.replace(first_path, first)\n    os.replace(second_path, second)\n'''
    assert _atomic_replace_without_fsync("main_review/example.py", source) == []


class _ResearchAdapter:
    name = "governed-research"

    def __init__(self, source: str) -> None:
        self.source = source

    def capabilities(self) -> set[str]:
        return {"research"}

    def lookup(self, request: dict, task: dict) -> dict:
        packet = evidence_packet(
            mission_id=task["mission_id"],
            task_id=task["task_id"],
            worker_id="Private-Research-1",
            claims=({"claim": "Current documentation confirms the contract."},),
            evidence_refs=("https://example.test/reference",),
            provenance={
                "adapter": self.name,
                "observed_at": "2026-07-17T00:00:00Z",
                "source": self.source,
                "retrieved_at": "2026-07-17T00:00:00Z",
                "supported_claim": "Current documentation confirms the contract.",
                "freshness": "current",
            },
            confidence=0.9,
        )
        return {**request, "status": "completed", "evidence_packet": packet}


def _research_campaign() -> dict:
    task = task_packet(
        mission_id="mission-1",
        officer="Scout",
        objective="Verify current documentation.",
        scope=("src/auth.py",),
        questions=("What does the current official contract require?",),
        required_evidence=("source and retrieval time",),
        allowed_capabilities=("research_lookup",),
    )
    request = research_request(
        mission_id="mission-1",
        task_id=task["task_id"],
        question="What does the current official contract require?",
        allowed_sources=("official_documentation",),
    )
    return {"tasks": [task], "workspace_requests": [], "research_requests": [request]}


def test_research_evidence_outside_allowed_sources_is_rejected() -> None:
    result = dispatch_authorized_requests(
        _research_campaign(), research=_ResearchAdapter("untrusted_blog")
    )
    assert result["evidence_packets"] == []
    assert result["research_results"][0]["status"] == "failed"


def test_research_evidence_from_allowed_source_is_admitted() -> None:
    result = dispatch_authorized_requests(
        _research_campaign(), research=_ResearchAdapter("official_documentation")
    )
    assert len(result["evidence_packets"]) == 1
    assert result["research_results"][0]["status"] == "completed"
''',
    encoding="utf-8",
)

Path(__file__).unlink(missing_ok=True)
(ROOT / ".github/workflows/build-workspace-rematch-round2.yml").unlink(missing_ok=True)
