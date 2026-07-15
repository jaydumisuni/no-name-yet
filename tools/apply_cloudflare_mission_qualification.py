from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[1]
cli_path = root / "main_review" / "cloudflare_cli.py"
workflow_path = root / ".github" / "workflows" / "cloudflare-live-certification.yml"
docs_path = root / "docs" / "27-cloudflare-live-certification.md"
test_path = root / "tests" / "test_cloudflare_mission_qualification.py"

cli = cli_path.read_text(encoding="utf-8")
if "def qualify_models(" not in cli:
    cli = replace_once(
        cli,
        "from .cpl_runtime import run_cpl_review\n",
        "from .cpl_reasoning import SPECIALISTS, specialist_system_prompt\n"
        "from .cpl_runtime import run_cpl_review\n",
        label="cpl reasoning import",
    )
    cli = replace_once(
        cli,
        "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, invoke_json\n",
        "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, invoke_json\n"
        "from .llm_review import (\n"
        "    SYSTEM_PROMPT,\n"
        "    _build_user_prompt,\n"
        "    _validate_pass,\n"
        "    collect_changed_file_excerpts,\n"
        ")\n",
        label="review contract imports",
    )
    cli = replace_once(
        cli,
        "COUNCIL_PROOF_MAX_OUTPUT_TOKENS = 1200\n",
        "COUNCIL_PROOF_MAX_OUTPUT_TOKENS = 1200\n"
        "MISSION_PROOF_MAX_OUTPUT_TOKENS = 1200\n"
        "MISSION_PROOF_TIMEOUT_SECONDS = 45.0\n",
        label="mission constants",
    )
    cli = replace_once(
        cli,
        "    max_output_tokens: int = COUNCIL_PROOF_MAX_OUTPUT_TOKENS,\n) -> LLMRoute:\n",
        "    max_output_tokens: int = COUNCIL_PROOF_MAX_OUTPUT_TOKENS,\n"
        "    timeout_seconds: float | None = None,\n"
        ") -> LLMRoute:\n",
        label="route timeout parameter",
    )
    cli = replace_once(
        cli,
        "        timeout_seconds=settings.timeout_seconds,\n",
        "        timeout_seconds=timeout_seconds or settings.timeout_seconds,\n",
        label="route timeout value",
    )

    insertion = '''\n\ndef _finding_matches_mission_contract(\n    finding: dict[str, Any],\n    *,\n    expected_path: str,\n    expected_category: str,\n    expected_severity: str,\n    expected_evidence: str,\n) -> bool:\n    if expected_path and str(finding.get("path") or "") != expected_path:\n        return False\n    if not _candidate_meets_expected_contract(\n        finding,\n        expected_category=expected_category,\n        expected_severity=expected_severity,\n        expected_evidence=expected_evidence,\n    ):\n        return False\n    return True\n\n\ndef qualify_models(\n    settings: CloudflareGatewaySettings,\n    *,\n    root: str | Path,\n    changed_files: list[str],\n    expected_verdict: str = "",\n    expected_path: str = "",\n    expected_category: str = "",\n    expected_severity: str = "",\n    expected_evidence: str = "",\n) -> dict[str, Any]:\n    """Qualify each model against Sergeant's full officer-review contract.\n\n    The lightweight route handshake proves JSON transport only. This mission\n    proof requires a model to complete an evidence-grounded Medic security\n    report before Cpl may admit it to the focused live council.\n    """\n\n    settings.validate()\n    root_path = Path(root)\n    files, excerpts = collect_changed_file_excerpts(root_path, changed_files)\n    if not files:\n        raise CloudflareGatewayError("Mission qualification requires at least one readable changed file.")\n\n    expected_verdict = expected_verdict.strip().upper()\n    expected_path = expected_path.strip()\n    expected_category = expected_category.strip().lower()\n    expected_severity = expected_severity.strip().lower()\n    expected_evidence = expected_evidence.strip().lower()\n    assignment = SPECIALISTS["security"]\n    context = {\n        "proof_type": "cloudflare-model-mission-qualification",\n        "changed_files": changed_files,\n        "rule": (\n            "Complete the supplied officer-support review contract from repository evidence. "\n            "Do not echo an expected answer or claim model independence."\n        ),\n    }\n    user_prompt = _build_user_prompt(changed_files, excerpts, context)\n    system_prompt = specialist_system_prompt(SYSTEM_PROMPT, assignment)\n    results: list[dict[str, Any]] = []\n\n    for model in settings.models:\n        route = cloudflare_route(\n            settings,\n            model=model,\n            max_output_tokens=MISSION_PROOF_MAX_OUTPUT_TOKENS,\n            timeout_seconds=min(settings.timeout_seconds, MISSION_PROOF_TIMEOUT_SECONDS),\n        )\n        started = time.monotonic()\n        try:\n            payload = invoke_json(route, system_prompt=system_prompt, user_prompt=user_prompt)\n            report = _validate_pass(payload, files, route=route, assignment=assignment)\n            matching = [\n                finding\n                for finding in report.get("findings", [])\n                if _finding_matches_mission_contract(\n                    finding,\n                    expected_path=expected_path,\n                    expected_category=expected_category,\n                    expected_severity=expected_severity,\n                    expected_evidence=expected_evidence,\n                )\n            ]\n            verdict_matches = not expected_verdict or report.get("verdict") == expected_verdict\n            passed = verdict_matches and bool(matching)\n            results.append({\n                "model": model,\n                "passed": passed,\n                "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                "max_output_tokens": MISSION_PROOF_MAX_OUTPUT_TOKENS,\n                "timeout_seconds": route.timeout_seconds,\n                "response": {\n                    "verdict": report.get("verdict"),\n                    "finding_count": len(report.get("findings", [])),\n                    "matching_findings": matching,\n                    "coverage": report.get("coverage", {}),\n                },\n            })\n        except LLMProviderError as error:\n            results.append({\n                "model": model,\n                "passed": False,\n                "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                "max_output_tokens": MISSION_PROOF_MAX_OUTPUT_TOKENS,\n                "timeout_seconds": route.timeout_seconds,\n                "error": str(error),\n            })\n\n    qualified = [str(item["model"]) for item in results if item.get("passed") is True]\n    return {\n        "provider": "cloudflare-workers-ai",\n        "proof_type": "mission_capability",\n        "model_count": len(settings.models),\n        "passed_count": len(qualified),\n        "qualified_models": qualified,\n        "all_passed": bool(results) and len(qualified) == len(results),\n        "expected_verdict": expected_verdict,\n        "expected_path": expected_path,\n        "expected_category": expected_category,\n        "expected_severity": expected_severity,\n        "expected_evidence": expected_evidence,\n        "models": results,\n    }\n'''
    cli = replace_once(
        cli,
        "\n\ndef _changed_files(value: str, file_list: str | None) -> list[str]:\n",
        insertion + "\n\ndef _changed_files(value: str, file_list: str | None) -> list[str]:\n",
        label="mission qualification functions",
    )

    parser_block = '''    test = sub.add_parser("test-models", help="Call every configured Cloudflare model with a structured-output proof.")\n    test.add_argument("--require", action="store_true")\n'''
    parser_replacement = parser_block + '''\n    qualify = sub.add_parser(\n        "qualify-models",\n        help="Call every configured model with Sergeant's full evidence-grounded officer contract.",\n    )\n    qualify.add_argument("path", nargs="?", default=".")\n    qualify_source = qualify.add_mutually_exclusive_group(required=True)\n    qualify_source.add_argument("--files", help="Comma/newline-separated changed files.")\n    qualify_source.add_argument("--file-list", help="File containing changed paths.")\n    qualify.add_argument("--expected-verdict", choices=sorted(VALID_COUNCIL_VERDICTS), default="")\n    qualify.add_argument("--expected-path", default="")\n    qualify.add_argument("--expected-category", default="")\n    qualify.add_argument("--expected-severity", default="")\n    qualify.add_argument("--expected-evidence", default="")\n    qualify.add_argument("--minimum-models", type=int, default=2)\n    qualify.add_argument("--require", action="store_true")\n'''
    cli = replace_once(cli, parser_block, parser_replacement, label="qualify parser")

    main_marker = '''    if args.command == "gateway":\n'''
    main_insertion = '''    if args.command == "qualify-models":\n        changed = _changed_files(args.files or "", args.file_list)\n        if not changed:\n            parser.error("At least one changed file is required.")\n        try:\n            payload = qualify_models(\n                settings,\n                root=args.path,\n                changed_files=changed,\n                expected_verdict=args.expected_verdict,\n                expected_path=args.expected_path,\n                expected_category=args.expected_category,\n                expected_severity=args.expected_severity,\n                expected_evidence=args.expected_evidence,\n            )\n        except CloudflareGatewayError as error:\n            payload = {\n                "provider": "cloudflare-workers-ai",\n                "proof_type": "mission_capability",\n                "passed_count": 0,\n                "error": str(error),\n            }\n        _print(payload, pretty=args.pretty)\n        passed = int(payload.get("passed_count", 0)) >= max(1, args.minimum_models)\n        return 0 if passed or not args.require else 2\n\n'''
    cli = replace_once(cli, main_marker, main_insertion + main_marker, label="qualify main command")

cli_path.write_text(cli, encoding="utf-8")

workflow = workflow_path.read_text(encoding="utf-8")
workflow = workflow.replace('SERGEANT_CPL_MAX_PASSES: "3"', 'SERGEANT_CPL_MAX_PASSES: "2"')
workflow = workflow.replace('SERGEANT_CPL_MAX_COUNCIL_MEMBERS: "3"', 'SERGEANT_CPL_MAX_COUNCIL_MEMBERS: "2"')

fixture_block = '''      - name: Create focused council fixture\n        shell: bash\n        run: |\n          set -euo pipefail\n          mkdir -p build/live-council-fixture/src\n          cat > build/live-council-fixture/src/auth.py <<'PY'\n          import subprocess\n\n          def run_user_command(request):\n              command = request.args.get("command")\n              return subprocess.run(command, shell=True)\n          PY\n\n'''
if workflow.count(fixture_block) != 1:
    raise RuntimeError(f"fixture block: expected one match, found {workflow.count(fixture_block)}")
workflow = workflow.replace(fixture_block, "", 1)
status_block = '''      - name: Capture credential-safe route status\n        shell: bash\n        run: |\n          set -euo pipefail\n          mkdir -p build\n          sergeant-cloudflare --pretty status > build/cloudflare-status.json\n\n'''
workflow = replace_once(workflow, status_block, status_block + fixture_block, label="move fixture before qualification")

model_test_block = '''      - name: Test every configured model once\n        shell: bash\n        run: |\n          set +e\n          sergeant-cloudflare --pretty test-models > build/cloudflare-model-proof.json\n          code=$?\n          set -e\n          echo "MODEL_PROOF_EXIT=$code" >> "$GITHUB_ENV"\n\n'''
mission_step = '''      - name: Qualify every model against the full officer mission\n        shell: bash\n        run: |\n          set +e\n          sergeant-cloudflare --pretty qualify-models build/live-council-fixture \\\n            --files src/auth.py \\\n            --expected-verdict BLOCK \\\n            --expected-path src/auth.py \\\n            --expected-category security \\\n            --expected-severity blocker \\\n            --expected-evidence shell=True \\\n            --minimum-models 2 \\\n            > build/cloudflare-mission-model-proof.json\n          code=$?\n          set -e\n          echo "MISSION_MODEL_PROOF_EXIT=$code" >> "$GITHUB_ENV"\n\n'''
if mission_step not in workflow:
    workflow = replace_once(workflow, model_test_block, model_test_block + mission_step, label="mission qualification workflow step")

workflow = replace_once(
    workflow,
    '          path = Path("build/cloudflare-model-proof.json")\n',
    '          path = Path("build/cloudflare-mission-model-proof.json")\n',
    label="select mission-qualified models",
)
workflow = replace_once(
    workflow,
    '          models = json.loads(Path("build/cloudflare-model-proof.json").read_text(encoding="utf-8"))\n          council = json.loads(Path("build/cloudflare-council-proof.json").read_text(encoding="utf-8"))\n',
    '          handshake = json.loads(Path("build/cloudflare-model-proof.json").read_text(encoding="utf-8"))\n          models = json.loads(Path("build/cloudflare-mission-model-proof.json").read_text(encoding="utf-8"))\n          council = json.loads(Path("build/cloudflare-council-proof.json").read_text(encoding="utf-8"))\n',
    label="summary reads mission proof",
)
workflow = replace_once(
    workflow,
    '              "schema_version": "sergeant.cloudflare-live-certification.v2",\n',
    '              "schema_version": "sergeant.cloudflare-live-certification.v3",\n',
    label="certification schema version",
)
workflow = replace_once(
    workflow,
    '              "structured_model_pass_count": models.get("passed_count", 0),\n',
    '              "structured_model_pass_count": handshake.get("passed_count", 0),\n              "mission_model_pass_count": models.get("passed_count", 0),\n',
    label="mission pass count",
)
workflow = replace_once(
    workflow,
    '            build/cloudflare-model-proof.json\n            build/cloudflare-certified-models.json\n',
    '            build/cloudflare-model-proof.json\n            build/cloudflare-mission-model-proof.json\n            build/cloudflare-certified-models.json\n',
    label="mission artifact upload",
)
workflow_path.write_text(workflow, encoding="utf-8")

docs = docs_path.read_text(encoding="utf-8")
section = '''\n## Mission-capable model admission\n\nThe lightweight model handshake proves only that a route can return a small JSON object. It does not admit a model to Cpl's live formation. The certification therefore performs a second, model-by-model qualification against the complete evidence-grounded Medic security-officer contract on the focused fixture.\n\nOnly models that return the expected `BLOCK` verdict, verified `shell=True` evidence, the required path/category/severity, and valid coverage are written to the certified council roster. Models that time out, return unparseable JSON, or satisfy only the toy handshake remain probationary.\n\nThe focused council uses two mission-qualified members and two initial passes: Cpl's general field pass and Medic's security support pass. The unrelated tests/contracts lens is intentionally not recruited for this one-file command-injection fixture; the general adaptive planner remains unchanged for ordinary repository reviews.\n'''
if "## Mission-capable model admission" not in docs:
    docs += section
docs_path.write_text(docs, encoding="utf-8")

test_path.write_text('''from __future__ import annotations\n\nfrom pathlib import Path\n\nimport pytest\n\nfrom main_review import cloudflare_cli\nfrom main_review.cloudflare_gateway import CloudflareGatewaySettings\n\n\ndef settings() -> CloudflareGatewaySettings:\n    return CloudflareGatewaySettings(\n        account_id="0123456789abcdef0123456789abcdef",\n        api_token="secret-token",\n        models=("@cf/qwen/model-a", "@cf/openai/model-b"),\n        host="127.0.0.1",\n        port=0,\n        timeout_seconds=75.0,\n        max_request_bytes=100_000,\n    )\n\n\ndef fixture(tmp_path: Path) -> Path:\n    root = tmp_path / "repo"\n    path = root / "src" / "auth.py"\n    path.parent.mkdir(parents=True)\n    path.write_text(\n        "import subprocess\\n\\n"\n        "def run_user_command(request):\\n"\n        "    command = request.args.get(\\\"command\\\")\\n"\n        "    return subprocess.run(command, shell=True)\\n",\n        encoding="utf-8",\n    )\n    return root\n\n\ndef valid_payload() -> dict[str, object]:\n    return {\n        "verdict": "BLOCK",\n        "confidence": 0.96,\n        "summary": "User input reaches shell execution.",\n        "findings": [\n            {\n                "severity": "blocker",\n                "category": "security",\n                "path": "src/auth.py",\n                "line_start": 5,\n                "line_end": 5,\n                "message": "Untrusted command reaches shell execution.",\n                "evidence": "return subprocess.run(command, shell=True)",\n                "why_it_matters": "An attacker can execute arbitrary shell commands.",\n                "safer_alternative": "Pass a validated argument vector with shell disabled.",\n            }\n        ],\n        "unanswered_questions": [],\n        "coverage": {"files_reviewed": ["src/auth.py"], "areas": ["security"]},\n    }\n\n\ndef test_mission_qualification_admits_only_full_officer_contracts(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    root = fixture(tmp_path)\n\n    def fake_invoke(route: object, *, system_prompt: str, user_prompt: str) -> dict[str, object]:\n        if getattr(route, "model").endswith("model-a"):\n            return valid_payload()\n        return {"status": "ready", "model": getattr(route, "model"), "capabilities": ["structured_json", "reasoning"]}\n\n    monkeypatch.setattr(cloudflare_cli, "invoke_json", fake_invoke)\n    result = cloudflare_cli.qualify_models(\n        settings(),\n        root=root,\n        changed_files=["src/auth.py"],\n        expected_verdict="BLOCK",\n        expected_path="src/auth.py",\n        expected_category="security",\n        expected_severity="blocker",\n        expected_evidence="shell=True",\n    )\n\n    assert result["passed_count"] == 1\n    assert result["qualified_models"] == ["@cf/qwen/model-a"]\n    assert result["models"][0]["passed"] is True\n    assert result["models"][1]["passed"] is False\n\n\ndef test_mission_qualification_rejects_unverified_evidence(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    root = fixture(tmp_path)\n    payload = valid_payload()\n    payload["findings"][0]["evidence"] = "not present in the file"\n    monkeypatch.setattr(cloudflare_cli, "invoke_json", lambda *args, **kwargs: payload)\n\n    result = cloudflare_cli.qualify_models(\n        settings(),\n        root=root,\n        changed_files=["src/auth.py"],\n        expected_verdict="BLOCK",\n        expected_path="src/auth.py",\n        expected_category="security",\n        expected_severity="blocker",\n        expected_evidence="shell=True",\n    )\n\n    assert result["passed_count"] == 0\n    assert all(item["passed"] is False for item in result["models"])\n\n\ndef test_live_workflow_uses_mission_qualified_two_member_roster() -> None:\n    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "cloudflare-live-certification.yml").read_text(encoding="utf-8")\n\n    assert "qualify-models build/live-council-fixture" in workflow\n    assert "build/cloudflare-mission-model-proof.json" in workflow\n    assert 'SERGEANT_CPL_MAX_PASSES: "2"' in workflow\n    assert 'SERGEANT_CPL_MAX_COUNCIL_MEMBERS: "2"' in workflow\n''', encoding="utf-8")

for path in (cli_path, workflow_path, docs_path, test_path):
    text = path.read_text(encoding="utf-8")
    if "apply_cloudflare_mission_qualification" in text:
        raise RuntimeError(f"temporary constructor leaked into {path}")

assert cli_path.read_text(encoding="utf-8").count("def qualify_models(") == 1
assert workflow_path.read_text(encoding="utf-8").count("cloudflare-mission-model-proof.json") >= 3
print("Cloudflare mission-qualification patch applied.")
