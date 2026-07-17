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
    """        if inline and inline not in literal_markers | folded_markers:
            command_lines.append(inline)
""",
    """        if inline and inline not in literal_markers | folded_markers:
            command_lines.append(_clean_yaml_scalar(inline))
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """def _executed_test_paths(text: str) -> set[str]:
    \"\"\"Return test paths appearing in actual runner invocations only.\"\"\"
""",
    """def _strip_shell_comment(command: str) -> str:
    \"\"\"Remove an unquoted shell comment without changing quoted hashes.\"\"\"

    quote: str | None = None
    escaped = False
    for index, character in enumerate(command):
        if escaped:
            escaped = False
            continue
        if character == \"\\\\\" and quote != \"'\":
            escaped = True
            continue
        if character in {\"'\", '\"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character == \"#\" and quote is None and (index == 0 or command[index - 1].isspace()):
            return command[:index].rstrip()
    return command


def _executed_test_paths(text: str) -> set[str]:
    \"\"\"Return test paths appearing in actual runner invocations only.\"\"\"
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        for logical in logical_lines:
            for segment in re.split(r\"\\s*(?:&&|\\|\\||;|\\|)\\s*\", logical):
""",
    """        for logical in logical_lines:
            logical = _strip_shell_comment(logical)
            if not logical:
                continue
            for segment in re.split(r\"\\s*(?:&&|\\|\\||;|\\|)\\s*\", logical):
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        for match in re.finditer(r\"(?:os\\\\.)?replace\\\\s*\\\\(\\\\s*([^,\\\\n]+)\\\\s*,\", body):
            replacements.append((match.start(), match.group(1).strip()))
""",
    """        for match in re.finditer(
            r\"(?:\\\\bos\\\\.replace|(?<![.\\\\w])replace)\\\\s*\\\\(\\\\s*([^,\\\\n]+)\\\\s*,\",
            body,
        ):
            replacements.append((match.start(), match.group(1).strip()))
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        for match in re.finditer(r\"\\\\b([A-Za-z_][A-Za-z0-9_]*)\\\\.replace\\\\s*\\\\(\", body):
            replacements.append((match.start(), match.group(1)))
""",
    """        known_path_receivers = set(aliases) | set(fd_paths)
        for match in re.finditer(
            r\"(?m)^\\\\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\\\\s*=\\\\s*\"
            r\"(?:pathlib\\\\.)?Path\\\\s*\\\\([^\\\\n]*\\\\)\"
            r\"|(?m)^\\\\s*(?P<class_name>[A-Za-z_][A-Za-z0-9_]*)\\\\s*=\\\\s*\"
            r\"[A-Za-z_][A-Za-z0-9_]*\\\\.__class__\\\\s*\\\\([^\\\\n]*\\\\)\"
            r\"|(?m)^\\\\s*(?P<method_name>[A-Za-z_][A-Za-z0-9_]*)\\\\s*=\\\\s*\"
            r\"[A-Za-z_][A-Za-z0-9_]*\\\\.(?:with_suffix|with_name|resolve|absolute)\\\\s*\\\\([^\\\\n]*\\\\)\",
            body,
        ):
            known_path_receivers.add(
                match.group(\"name\") or match.group(\"class_name\") or match.group(\"method_name\")
            )
        for match in re.finditer(r\"\\\\b([A-Za-z_][A-Za-z0-9_]*)\\\\.replace\\\\s*\\\\(\", body):
            receiver = match.group(1)
            if receiver in known_path_receivers:
                replacements.append((match.start(), receiver))
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """        non_durable: list[str] = []
        for replace_pos, source in sorted(replacements):
""",
    """        non_durable: list[str] = []
        publication_boundaries: dict[str, int] = {}
        for replace_pos, source in sorted(replacements):
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """                durable = any(
                    write < flush < fsync < replace_pos
                    for write in write_positions
                    for flush in flush_positions
                    for fsync in fsync_positions
                )
""",
    """                identity = f\"handle:{handle}\"
                lower_bound = publication_boundaries.get(identity, -1)
                durable = any(
                    lower_bound < write < flush < fsync < replace_pos
                    for write in write_positions
                    for flush in flush_positions
                    for fsync in fsync_positions
                )
                if durable:
                    publication_boundaries[identity] = replace_pos
""",
)

replace_once(
    "main_review/offline_investigation.py",
    """                durable = any(write < fsync < replace_pos for write in writes for fsync in fsyncs)
""",
    """                identity = f\"fd:{fd}\"
                lower_bound = publication_boundaries.get(identity, -1)
                durable = any(lower_bound < write < fsync < replace_pos for write in writes for fsync in fsyncs)
                if durable:
                    publication_boundaries[identity] = replace_pos
""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """def _validate_adapter_evidence(
    result: dict[str, Any],
    task: dict[str, Any],
    *,
    adapter_name: str,
    research: bool,
) -> dict[str, Any] | None:
""",
    """def _validate_adapter_evidence(
    result: dict[str, Any],
    task: dict[str, Any],
    *,
    request: dict[str, Any],
    adapter_name: str,
    research: bool,
) -> dict[str, Any] | None:
""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """    if provenance.get(\"adapter\") != adapter_name:
        raise ValueError(\"adapter evidence provenance does not match the executing adapter\")
    return validate_evidence_packet(packet, task)
""",
    """    if provenance.get(\"adapter\") != adapter_name:
        raise ValueError(\"adapter evidence provenance does not match the executing adapter\")
    if research:
        allowed_sources = {str(item).strip() for item in request.get(\"allowed_sources\", []) if str(item).strip()}
        if str(provenance.get(\"source\") or \"\").strip() not in allowed_sources:
            raise ValueError(\"research evidence source is outside the authorized source policy\")
    return validate_evidence_packet(packet, task)
""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """            packet = _validate_adapter_evidence(result, task, adapter_name=workspace.name, research=False)
""",
    """            packet = _validate_adapter_evidence(
                result, task, request=request, adapter_name=workspace.name, research=False
            )
""",
)

replace_once(
    "main_review/workspace_interfaces.py",
    """            packet = _validate_adapter_evidence(result, task, adapter_name=research.name, research=True)
""",
    """            packet = _validate_adapter_evidence(
                result, task, request=request, adapter_name=research.name, research=True
            )
""",
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


def test_path_method_publication_remains_visible() -> None:
    source = '''\ndef save(path, payload):\n    temporary = path.with_suffix(".tmp")\n    temporary.write_text(payload)\n    temporary.replace(path)\n'''
    assert len(_atomic_replace_without_fsync("main_review/example.py", source)) == 1


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

for relative in (
    "scripts/apply_workspace_rematch_round2_fixes.py",
    ".github/workflows/build-workspace-rematch-round2.yml",
    "scripts/postfix_workspace_rematch_product.py",
    "scripts/apply_final_workspace_rematch.py",
    ".github/workflows/apply-final-rematch-repair.yml",
):
    (ROOT / relative).unlink(missing_ok=True)
