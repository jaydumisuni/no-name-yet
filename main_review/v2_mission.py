"""Sergeant V2 command-system layer.

V2 is internal-first: this module adds mission intake, briefing, armoury,
loadout, officer blueprint, confidence, and audit packets without replacing the
V1 review engine or breaking existing app/IDE contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .languages import classify_role, detect_language
from .scanner import scan_repository

V2_CONTRACT_VERSION = "sergeant.mission.v2"

MissionType = Literal[
    "repository_review",
    "pull_request_review",
    "changed_files_review",
    "single_file_review",
    "security_review",
    "architecture_review",
    "performance_review",
    "regression_review",
    "documentation_review",
    "benchmark_review",
    "learning_review",
    "emergency_review",
    "external_review_comparison",
    "release_gate_review",
]

MISSION_TYPES: set[str] = {
    "repository_review",
    "pull_request_review",
    "changed_files_review",
    "single_file_review",
    "security_review",
    "architecture_review",
    "performance_review",
    "regression_review",
    "documentation_review",
    "benchmark_review",
    "learning_review",
    "emergency_review",
    "external_review_comparison",
    "release_gate_review",
}

MODE_TO_MISSION = {
    "repository": "repository_review",
    "pull_request": "pull_request_review",
    "changed_files": "changed_files_review",
}

OFFICER_ORDER = [
    "quartermaster",
    "scout",
    "engineer",
    "medic",
    "mechanic",
    "analyst",
    "challenger",
    "archivist",
    "judge",
    "hermes",
]


@dataclass(frozen=True)
class MissionRequest:
    schema_version: str = V2_CONTRACT_VERSION
    source: str = "app-bridge"
    root: str = "."
    mission_type: str = "repository_review"
    mode: str = "repository"
    changed_files: list[str] = field(default_factory=list)
    branch: str | None = None
    commit: str | None = None
    pull_request: dict[str, Any] = field(default_factory=dict)
    external_providers: list[dict[str, Any]] = field(default_factory=list)
    human_decisions: list[dict[str, Any]] = field(default_factory=list)
    policy_profile: str = "default"
    enterprise_profile: dict[str, Any] = field(default_factory=dict)
    time_budget: dict[str, Any] = field(default_factory=lambda: {"seconds": 120})
    execution_permissions: dict[str, bool] = field(default_factory=lambda: {
        "read_only": True,
        "allow_shell": False,
        "allow_network": False,
        "allow_write": False,
        "allow_untrusted_code": False,
    })
    output_preferences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeaponManifest:
    weapon_id: str
    name: str
    category: str
    version: str
    status: str
    owner: str
    supported_languages: list[str]
    supported_frameworks: list[str]
    mission_profiles: list[str]
    officer_compatibility: list[str]
    input_schema: str
    output_schema: str
    permissions_required: list[str]
    executes_code: bool
    requires_network: bool
    modifies_files: bool
    average_runtime_ms: int
    confidence_behavior: str
    failure_behavior: str
    test_requirements: list[str]
    evidence_output_type: str
    maturity_level: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OfficerBlueprint:
    identity: str
    mission: str
    authority: str
    restrictions: list[str]
    universal_training_access: list[str]
    investigation_pipeline: list[str]
    evidence_rules: list[str]
    report_format: str
    test_requirements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    raise TypeError("value must be a string, list, or null")


def _clean_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean_dict_list(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def normalize_mission_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise TypeError("mission request must be a dictionary")

    mode = str(request.get("mode") or "repository")
    mission_type = str(request.get("mission_type") or MODE_TO_MISSION.get(mode) or "repository_review")
    if mission_type not in MISSION_TYPES:
        raise ValueError(f"mission_type must be one of {sorted(MISSION_TYPES)}")

    permissions = MissionRequest().execution_permissions | _clean_dict(request.get("execution_permissions"))
    normalized = MissionRequest(
        source=str(request.get("source") or "app-bridge"),
        root=str(request.get("root") or "."),
        mission_type=mission_type,
        mode=mode,
        changed_files=_clean_list(request.get("changed_files")),
        branch=request.get("branch"),
        commit=request.get("commit"),
        pull_request=_clean_dict(request.get("pull_request")),
        external_providers=_clean_dict_list(request.get("external_providers")),
        human_decisions=_clean_dict_list(request.get("human_decisions")),
        policy_profile=str(request.get("policy_profile") or "default"),
        enterprise_profile=_clean_dict(request.get("enterprise_profile")),
        time_budget=MissionRequest().time_budget | _clean_dict(request.get("time_budget")),
        execution_permissions={key: bool(value) for key, value in permissions.items()},
        output_preferences=_clean_dict(request.get("output_preferences")),
    )
    return normalized.to_dict()


def _detect_frameworks(paths: list[str], manifests: list[str]) -> list[str]:
    lower_paths = {path.lower() for path in paths + manifests}
    frameworks: set[str] = set()
    if "package.json" in lower_paths:
        frameworks.add("Node.js")
    if "pyproject.toml" in lower_paths or "requirements.txt" in lower_paths:
        frameworks.add("Python")
    if "go.mod" in lower_paths:
        frameworks.add("Go modules")
    if "cargo.toml" in lower_paths:
        frameworks.add("Cargo")
    if "pom.xml" in lower_paths or "build.gradle" in lower_paths:
        frameworks.add("JVM")
    if any("django" in path for path in lower_paths):
        frameworks.add("Django")
    if any("flask" in path for path in lower_paths):
        frameworks.add("Flask")
    if any("react" in path or path.endswith(".tsx") or path.endswith(".jsx") for path in lower_paths):
        frameworks.add("React")
    return sorted(frameworks)


def _detect_package_managers(manifests: list[str]) -> list[str]:
    mapping = {
        "pyproject.toml": "pip/pyproject",
        "requirements.txt": "pip",
        "package.json": "npm",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "go.mod": "go",
        "cargo.toml": "cargo",
        "pom.xml": "maven",
        "build.gradle": "gradle",
    }
    found = []
    lower = {manifest.lower() for manifest in manifests}
    for name, manager in mapping.items():
        if name in lower:
            found.append(manager)
    return sorted(set(found))


def _detect_build_systems(paths: list[str]) -> list[str]:
    lower = {path.lower() for path in paths}
    systems = set()
    if "makefile" in lower:
        systems.add("make")
    if "package.json" in lower:
        systems.add("npm scripts")
    if "pyproject.toml" in lower:
        systems.add("pyproject")
    if "dockerfile" in lower:
        systems.add("docker")
    if "cargo.toml" in lower:
        systems.add("cargo")
    if "go.mod" in lower:
        systems.add("go")
    return sorted(systems)


def build_mission_briefing(root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    insight = scan_repository(root_path).to_dict()
    files = [str(file.get("path")) for file in insight.get("files", []) if isinstance(file, dict)]
    changed = list(request.get("changed_files", []))
    changed_roles = {path: classify_role(path) for path in changed}
    changed_languages = {path: detect_language(path) for path in changed}
    ci_files = [path for path in files if path.startswith(".github/workflows/")]
    risk_level = "high" if insight.get("high_risk_files") or any(role in {"infrastructure", "sensitive"} for role in changed_roles.values()) else "medium" if changed else "low"
    return {
        "schema_version": V2_CONTRACT_VERSION,
        "repository": {"root": str(root_path), "name": root_path.name, "public": None},
        "mission_type": request.get("mission_type"),
        "changed_files": changed,
        "detected_languages": insight.get("languages", {}),
        "detected_frameworks": _detect_frameworks(files, list(insight.get("manifests", []))),
        "package_managers": _detect_package_managers(list(insight.get("manifests", []))),
        "build_systems": _detect_build_systems(files),
        "testing_frameworks": sorted({Path(path).parent.name for path in insight.get("tests", []) if Path(path).parent.name}),
        "ci_cd_systems": ["GitHub Actions"] if ci_files else [],
        "database_technologies": sorted({path for path in files if path.endswith(".sql")})[:10],
        "cloud_platform_technologies": sorted({path for path in files if any(part in path.lower() for part in ("terraform", "docker", "k8s", "helm", "cloudflare", "azure", "aws"))})[:10],
        "authentication_payment_security_surfaces": sorted({path for path in files if any(part in path.lower() for part in ("auth", "jwt", "token", "secret", "payment", "stripe", "pay"))})[:10],
        "documentation_surfaces": insight.get("docs", []),
        "external_evidence_sources": sorted({str(provider.get("source") or provider.get("name") or "external") for provider in request.get("external_providers", []) if isinstance(provider, dict)}),
        "risk_level": risk_level,
        "business_domain_clues": _domain_clues(files),
        "file_roles": changed_roles,
        "changed_file_languages": changed_languages,
        "dependency_map_summary": {"available": True, "source_file_count": sum(1 for file in insight.get("files", []) if isinstance(file, dict) and file.get("role") in {"source", "ui", "database"})},
        "allowed_operations": request.get("execution_permissions", {}),
        "time_budget": request.get("time_budget", {}),
        "output_target": request.get("output_preferences", {}).get("target", "json"),
    }


def _domain_clues(paths: list[str]) -> list[str]:
    clues = set()
    joined = " ".join(path.lower() for path in paths)
    for clue in ["payment", "auth", "ai", "ml", "cloud", "github", "ide", "review", "security"]:
        if clue in joined:
            clues.add(clue)
    return sorted(clues)


def default_weapon_manifests() -> list[dict[str, Any]]:
    weapons = [
        ("repository_scanner", "Repository Scanner", "analysis", ["quartermaster", "scout"], ["repository_review", "pull_request_review", "changed_files_review", "release_gate_review"], "battle_proven"),
        ("language_detector", "Programming Language Detector", "knowledge", ["scout", "engineer", "analyst"], list(MISSION_TYPES), "battle_proven"),
        ("capability_engine", "Static Capability Engine", "analysis", ["engineer", "medic", "mechanic", "analyst"], ["pull_request_review", "changed_files_review", "security_review", "architecture_review", "performance_review", "regression_review", "release_gate_review"], "field_tested"),
        ("evidence_consensus", "Evidence Consensus", "evidence", ["challenger", "analyst", "judge"], ["external_review_comparison", "pull_request_review", "release_gate_review"], "field_tested"),
        ("review_memory", "Verified Review Memory", "evidence", ["archivist", "judge"], ["learning_review", "pull_request_review", "release_gate_review"], "testing"),
        ("github_live_reader", "Read-only GitHub Evidence Reader", "evidence", ["challenger", "hermes"], ["pull_request_review", "security_review", "external_review_comparison", "release_gate_review"], "field_tested"),
        ("markdown_renderer", "Markdown Renderer", "delivery", ["hermes"], list(MISSION_TYPES), "battle_proven"),
        ("json_renderer", "JSON Renderer", "delivery", ["hermes"], list(MISSION_TYPES), "battle_proven"),
    ]
    manifests = []
    for weapon_id, name, category, officers, missions, maturity in weapons:
        manifests.append(WeaponManifest(
            weapon_id=weapon_id,
            name=name,
            category=category,
            version="2.0",
            status="approved" if maturity in {"battle_proven", "field_tested"} else "testing",
            owner="Sergeant",
            supported_languages=["*"],
            supported_frameworks=["*"],
            mission_profiles=missions,
            officer_compatibility=officers,
            input_schema=V2_CONTRACT_VERSION,
            output_schema="sergeant.evidence.v2",
            permissions_required=["read"],
            executes_code=False,
            requires_network=weapon_id == "github_live_reader",
            modifies_files=False,
            average_runtime_ms=250,
            confidence_behavior="Raises confidence when direct evidence is present; lowers confidence when context is missing.",
            failure_behavior="Report weapon_failed and continue with reduced confidence when mission allows.",
            test_requirements=["unit", "contract", "fixture"],
            evidence_output_type="structured_json",
            maturity_level=maturity,
        ).to_dict())
    return manifests


def officer_blueprints() -> dict[str, dict[str, Any]]:
    missions = {
        "quartermaster": "prepare mission logistics and shared context",
        "scout": "understand repository terrain",
        "engineer": "protect architecture and API contracts",
        "medic": "protect security and unsafe data flow",
        "mechanic": "protect runtime behavior",
        "analyst": "organize findings into decision-ready evidence",
        "challenger": "pressure-test disagreement and external evidence",
        "archivist": "preserve verified lessons",
        "judge": "measure trust and confidence",
        "hermes": "deliver accurate reports",
    }
    return {
        officer: OfficerBlueprint(
            identity=officer,
            mission=mission,
            authority="advise",
            restrictions=["read_only", "no_final_command", "no_untrusted_execution"],
            universal_training_access=["human_language_awareness", "programming_language_detection", "git_diffs", "evidence_formatting", "false_positive_discipline"],
            investigation_pipeline=["receive_briefing", "equip_loadout", "collect_evidence", "report_confidence"],
            evidence_rules=["cite_path_when_available", "do_not_invent_evidence", "mark_unknown_when_context_missing"],
            report_format="sergeant.officer_report.v2",
            test_requirements=["officer_report_contract", "mission_profile_coverage"],
        ).to_dict()
        for officer, mission in missions.items()
    }


def deployed_officers(mission_type: str, briefing: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    risk = briefing.get("risk_level")
    changed_roles = set((briefing.get("file_roles") or {}).values())
    deploy = {"quartermaster", "scout", "analyst", "hermes"}
    if mission_type in {"pull_request_review", "changed_files_review", "release_gate_review"}:
        deploy |= {"engineer", "challenger", "judge"}
    if mission_type in {"security_review", "release_gate_review"} or risk == "high":
        deploy |= {"medic", "judge", "challenger"}
    if mission_type in {"performance_review", "regression_review", "release_gate_review"}:
        deploy |= {"mechanic", "judge"}
    if mission_type in {"learning_review", "release_gate_review"}:
        deploy.add("archivist")
    if "documentation" in changed_roles and len(changed_roles) == 1:
        deploy &= {"quartermaster", "scout", "analyst", "hermes"}
    skipped = {officer: _skip_reason(officer, mission_type, risk) for officer in OFFICER_ORDER if officer not in deploy}
    return [officer for officer in OFFICER_ORDER if officer in deploy], skipped


def _skip_reason(officer: str, mission_type: str, risk: object) -> str:
    return f"{officer} not required for {mission_type} with {risk or 'unknown'} risk briefing."


def select_loadout(mission_type: str, officers: list[str], request: dict[str, Any]) -> dict[str, Any]:
    permissions = request.get("execution_permissions", {})
    manifests = default_weapon_manifests()
    loadouts: dict[str, list[dict[str, Any]]] = {officer: [] for officer in officers}
    unavailable: list[dict[str, str]] = []
    for weapon in manifests:
        if mission_type not in weapon["mission_profiles"] and "*" not in weapon["mission_profiles"]:
            continue
        if weapon["requires_network"] and not permissions.get("allow_network"):
            unavailable.append({"weapon_id": weapon["weapon_id"], "reason": "network permission not granted"})
            continue
        if weapon["executes_code"] and not permissions.get("allow_untrusted_code"):
            unavailable.append({"weapon_id": weapon["weapon_id"], "reason": "code execution permission not granted"})
            continue
        for officer in officers:
            if officer in weapon["officer_compatibility"] and len(loadouts[officer]) < 3:
                loadouts[officer].append(weapon)
    return {
        "strategy": "minimal_effective_loadout",
        "deployed_officers": officers,
        "officer_loadouts": loadouts,
        "unavailable_weapons": unavailable,
        "weapon_manifest": manifests,
    }


def adaptive_confidence(briefing: dict[str, Any], loadout: dict[str, Any], evidence_consensus: dict[str, Any] | None = None) -> dict[str, Any]:
    consensus = evidence_consensus or {}
    evidence_count = int((consensus.get("summary") or {}).get("total_findings") or 0) if isinstance(consensus.get("summary"), dict) else 0
    officer_count = len(loadout.get("deployed_officers", []))
    unavailable_count = len(loadout.get("unavailable_weapons", []))
    risk = briefing.get("risk_level")
    base = 0.72 + min(0.12, officer_count * 0.01) + min(0.08, evidence_count * 0.01) - min(0.18, unavailable_count * 0.04)
    if risk == "high":
        base -= 0.04
    mission_confidence = round(max(0.1, min(0.98, base)), 2)
    return {
        "mission_confidence": mission_confidence,
        "finding_confidence_basis": "evidence_count, officer coverage, weapon availability, risk level",
        "officer_confidence": {officer: round(max(0.1, min(0.98, mission_confidence - 0.03 + index * 0.005)), 2) for index, officer in enumerate(loadout.get("deployed_officers", []))},
        "confidence_adjustments": {
            "risk_level": risk,
            "evidence_count": evidence_count,
            "unavailable_weapon_count": unavailable_count,
        },
    }


def audit_trail(mission: dict[str, Any], officers: list[str], loadout: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [
        ("mission_received", {"mission_type": mission.get("mission_type"), "source": mission.get("source")}),
        ("briefing_created", {"changed_file_count": len(mission.get("changed_files", []))}),
        ("officers_deployed", {"officers": officers}),
    ]
    for officer in officers:
        entries.append(("weapons_equipped", {"officer": officer, "weapon_count": len(loadout.get("officer_loadouts", {}).get(officer, []))}))
    entries.extend([
        ("consensus_created", {"status": "pending_or_external"}),
        ("command_issued", {"commander": "Sergeant"}),
        ("report_delivered", {"target": mission.get("output_preferences", {}).get("target", "json")}),
    ])
    return [{"event": event, "details": details} for event, details in entries]


def run_v2_mission(request: dict[str, Any], *, evidence_consensus: dict[str, Any] | None = None) -> dict[str, Any]:
    mission = normalize_mission_request(request)
    briefing = build_mission_briefing(mission["root"], mission)
    officers, skipped = deployed_officers(str(mission["mission_type"]), briefing)
    loadout = select_loadout(str(mission["mission_type"]), officers, mission)
    confidence = adaptive_confidence(briefing, loadout, evidence_consensus)
    return {
        "ok": True,
        "schema_version": V2_CONTRACT_VERSION,
        "service": "Sergeant V2 Mission System",
        "commander": "Sergeant",
        "doctrine": {
            "highest_law": "Sergeant commands. Specialists advise. Evidence decides.",
            "evidence_before_opinion": True,
            "stable_outside_adaptive_inside": True,
        },
        "mission": mission,
        "mission_briefing": briefing,
        "shared_services": [
            "language_detection_service",
            "programming_language_detection_service",
            "framework_detection_service",
            "repository_profile_service",
            "file_role_classifier",
            "diff_parser",
            "evidence_formatter",
            "mission_cache",
            "repository_search",
            "memory_lookup",
            "policy_loader",
            "knowledge_pack_loader",
            "armoury_registry",
            "confidence_service",
            "telemetry_logger",
        ],
        "officer_blueprints": officer_blueprints(),
        "deployment": {
            "deployed_officers": officers,
            "skipped_officers": skipped,
        },
        "armoury": loadout,
        "confidence": confidence,
        "audit": audit_trail(mission, officers, loadout),
        "interfaces": {
            "stable": ["CLI", "App Bridge", "GitHub", "VS Code", "JetBrains"],
            "optional_v2_fields": True,
            "hunter_dependency": "not_public_required",
        },
        "safety": {
            "read_only_default": True,
            "executes_untrusted_code": False,
            "modifies_files": False,
            "write_token_required": False,
        },
    }
