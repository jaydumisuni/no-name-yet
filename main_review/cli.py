"""Command line entrypoint for Sergeant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app_bridge import handle_app_review_request
from .battle_compare import run_battle_comparison
from .battle_tests import validate_battle_fixtures
from .boundary import check_action_boundary, repository_visibility_policy
from .capability_engine import run_capability_engine
from .diff_review import parse_changed_files_text, review_changed_files, review_changed_files_file
from .evidence import collect_evidence
from .final_proof import assert_final_proof, run_final_proof
from .github_collector import collect_github_comments_file
from .github_live_fetch import fetch_pr_comments_live
from .ide_bench import build_ide_bench_contract
from .memory import ReviewMemoryStore, default_memory_path, new_memory_record
from .memory_ingestion import write_learning_candidates_to_memory
from .proof_suite import assert_end_to_end_proof, run_end_to_end_proof
from .review_batch import batch_summary, run_review_learning_batch
from .review_contract import github_comments_to_external_provider, load_review_request_file
from .review_ingestion import ingest_external_review_file
from .scanner import scan_repository
from .verdict import review_repository
from .verification import verify_repository_standard
from .v2_mission import MISSION_TYPES, run_v2_mission


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sergeant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Build a static repository intelligence packet.")
    scan_parser.add_argument("path", nargs="?", default=".")
    scan_parser.add_argument("--pretty", action="store_true")

    evidence_parser = subparsers.add_parser("evidence", help="Collect static review evidence without executing project code.")
    evidence_parser.add_argument("path", nargs="?", default=".")
    evidence_parser.add_argument("--pretty", action="store_true")

    review_parser = subparsers.add_parser("review", help="Run static evidence collection and produce a verdict.")
    review_parser.add_argument("path", nargs="?", default=".")
    review_parser.add_argument("--pretty", action="store_true")

    v2_parser = subparsers.add_parser("v2-mission", help="Build the Sergeant V2 mission, briefing, loadout, confidence, and audit packet.")
    v2_parser.add_argument("path", nargs="?", default=".")
    v2_parser.add_argument("--mission-type", default="repository_review", choices=sorted(MISSION_TYPES))
    v2_parser.add_argument("--mode", default="repository", choices=["repository", "pull_request", "changed_files"])
    v2_source = v2_parser.add_mutually_exclusive_group()
    v2_source.add_argument("--files")
    v2_source.add_argument("--file-list")
    v2_parser.add_argument("--source", default="cli:v2-mission")
    v2_parser.add_argument("--allow-network", action="store_true")
    v2_parser.add_argument("--allow-shell", action="store_true")
    v2_parser.add_argument("--allow-write", action="store_true")
    v2_parser.add_argument("--allow-untrusted-code", action="store_true")
    v2_parser.add_argument("--pretty", action="store_true")

    app_parser = subparsers.add_parser("app-review", help="Run Sergeant through the app-facing bridge.")
    app_parser.add_argument("path", nargs="?", default=".")
    app_parser.add_argument("--mode", default="repository", choices=["repository", "pull_request", "changed_files"])
    app_source = app_parser.add_mutually_exclusive_group()
    app_source.add_argument("--files")
    app_source.add_argument("--file-list")
    app_parser.add_argument("--external-review-file")
    app_parser.add_argument("--request-file", help="JSON request using the shared Sergeant review contract.")
    app_parser.add_argument("--pretty", action="store_true")

    capability_parser = subparsers.add_parser("capability-review", help="Run Sergeant Tier 1 capability analysis.")
    capability_parser.add_argument("path", nargs="?", default=".")
    capability_source = capability_parser.add_mutually_exclusive_group()
    capability_source.add_argument("--files")
    capability_source.add_argument("--file-list")
    capability_parser.add_argument("--pretty", action="store_true")

    live_parser = subparsers.add_parser("live-github-comments", help="Read-only live GitHub PR comments fetch.")
    live_parser.add_argument("repository", help="Repository in owner/name form.")
    live_parser.add_argument("pr_number", type=int, help="Pull request number.")
    live_parser.add_argument("--token", default=None, help="Optional read-only GitHub token.")
    live_parser.add_argument("--base-url", default="https://api.github.com")
    live_parser.add_argument("--pretty", action="store_true")

    live_review_parser = subparsers.add_parser("live-github-review", help="Fetch live GitHub comments and run them through the app bridge.")
    live_review_parser.add_argument("repository", help="Repository in owner/name form.")
    live_review_parser.add_argument("pr_number", type=int, help="Pull request number.")
    live_review_parser.add_argument("path", nargs="?", default=".")
    live_review_parser.add_argument("--mode", default="pull_request", choices=["repository", "pull_request", "changed_files"])
    live_review_source = live_review_parser.add_mutually_exclusive_group()
    live_review_source.add_argument("--files")
    live_review_source.add_argument("--file-list")
    live_review_parser.add_argument("--token", default=None, help="Optional read-only GitHub token.")
    live_review_parser.add_argument("--base-url", default="https://api.github.com")
    live_review_parser.add_argument("--pretty", action="store_true")

    ide_parser = subparsers.add_parser("ide-bench-contract", help="Print the VS Code, PyCharm, JetBrains, and AI handoff contract.")
    ide_parser.add_argument("--pretty", action="store_true")

    battle_parser = subparsers.add_parser("battle-tests", help="Validate local battle-test fixtures and static comparisons.")
    battle_parser.add_argument("path", nargs="?", default=".")
    battle_parser.add_argument("--pretty", action="store_true")

    battle_compare_parser = subparsers.add_parser("battle-compare", help="Fetch a real PR patch, run Sergeant, and compare expected battle findings.")
    battle_compare_parser.add_argument("fixture", help="Path to one battle-tests/*.json fixture.")
    battle_compare_parser.add_argument("--token", default=None, help="Optional read-only GitHub token.")
    battle_compare_parser.add_argument("--base-url", default="https://api.github.com")
    battle_compare_parser.add_argument("--match-threshold", type=float, default=0.5)
    battle_compare_parser.add_argument("--pretty", action="store_true")

    boundary_parser = subparsers.add_parser("boundary", help="Check Sergeant public safety boundary.")
    boundary_parser.add_argument("action")
    boundary_parser.add_argument("--requires-write-token", action="store_true")
    boundary_parser.add_argument("--executes-untrusted-code", action="store_true")
    boundary_parser.add_argument("--pretty", action="store_true")

    visibility_parser = subparsers.add_parser("visibility-policy", help="Show public/private split guidance.")
    visibility_parser.add_argument("--private", action="store_true")
    visibility_parser.add_argument("--pretty", action="store_true")

    verify_parser = subparsers.add_parser("verify-standard", help="Check THETECHGUY engineering verification evidence.")
    verify_parser.add_argument("path", nargs="?", default=".")
    verify_parser.add_argument("--pretty", action="store_true")

    final_parser = subparsers.add_parser("final-proof", help="Run final PASS + verified proof gate.")
    final_parser.add_argument("path", nargs="?", default=".")
    final_parser.add_argument("--pretty", action="store_true")
    final_parser.add_argument("--no-fail", action="store_true")

    suite_parser = subparsers.add_parser("proof-suite", help="Run end-to-end proof across local review phases.")
    suite_parser.add_argument("path", nargs="?", default=".")
    suite_parser.add_argument("--pretty", action="store_true")
    suite_parser.add_argument("--no-fail", action="store_true")

    diff_parser = subparsers.add_parser("diff-review", help="Review a changed-file list without executing project code.")
    diff_source = diff_parser.add_mutually_exclusive_group(required=True)
    diff_source.add_argument("--files")
    diff_source.add_argument("--file-list")
    diff_parser.add_argument("--pretty", action="store_true")

    collect_parser = subparsers.add_parser("collect-github-comments", help="Normalize exported GitHub PR comments into ingestion JSON.")
    collect_parser.add_argument("path")
    collect_parser.add_argument("--repository", default="")
    collect_parser.add_argument("--pr-number", type=int, default=None)
    collect_parser.add_argument("--pretty", action="store_true")

    batch_parser = subparsers.add_parser("review-batch", help="Run collect -> ingest -> optional memory write for PR comments.")
    batch_parser.add_argument("path")
    batch_parser.add_argument("--root", default=".")
    batch_parser.add_argument("--repository", default="")
    batch_parser.add_argument("--pr-number", type=int, default=None)
    batch_parser.add_argument("--write-memory", action="store_true")
    batch_parser.add_argument("--status", default="proposed", choices=["proposed", "verified", "superseded", "rejected"])
    batch_parser.add_argument("--tag", action="append", default=[])
    batch_parser.add_argument("--summary-only", action="store_true")
    batch_parser.add_argument("--pretty", action="store_true")

    ingest_parser = subparsers.add_parser("ingest-review", help="Ingest exported external reviewer comments.")
    ingest_parser.add_argument("path")
    ingest_parser.add_argument("--pretty", action="store_true")

    learn_parser = subparsers.add_parser("learn-review", help="Write accepted external review learning candidates into Review Memory.")
    learn_parser.add_argument("path")
    learn_parser.add_argument("--root", default=".")
    learn_parser.add_argument("--status", default="proposed", choices=["proposed", "verified", "superseded", "rejected"])
    learn_parser.add_argument("--tag", action="append", default=[])
    learn_parser.add_argument("--pretty", action="store_true")

    memory_parser = subparsers.add_parser("memory", help="Manage review memory records.")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)
    add_parser = memory_subparsers.add_parser("add")
    add_parser.add_argument("--root", default=".")
    add_parser.add_argument("--kind", required=True, choices=["decision", "lesson", "principle", "boundary", "risk"])
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--summary", required=True)
    add_parser.add_argument("--reason", required=True)
    add_parser.add_argument("--status", default="proposed", choices=["proposed", "verified", "superseded", "rejected"])
    add_parser.add_argument("--scope", default="repository")
    add_parser.add_argument("--evidence", action="append", default=[])
    add_parser.add_argument("--tag", action="append", default=[])
    add_parser.add_argument("--applies-to", action="append", default=[])
    add_parser.add_argument("--confidence", type=float, default=0.5)
    list_parser = memory_subparsers.add_parser("list")
    list_parser.add_argument("--root", default=".")
    list_parser.add_argument("--kind")
    list_parser.add_argument("--status")
    list_parser.add_argument("--tag")
    list_parser.add_argument("--pretty", action="store_true")
    search_parser = memory_subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--root", default=".")
    search_parser.add_argument("--pretty", action="store_true")
    return parser


def _print_json(payload: object, *, pretty: bool = False) -> None:
    print(json.dumps(payload, indent=2 if pretty else None, sort_keys=True))


def _changed_from_args(files: str | None, file_list: str | None) -> list[str]:
    if file_list:
        return parse_changed_files_text(Path(file_list).read_text(encoding="utf-8"))
    return parse_changed_files_text(files or "")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        _print_json(scan_repository(Path(args.path)).to_dict(), pretty=args.pretty)
        return 0
    if args.command == "evidence":
        _print_json(collect_evidence(Path(args.path)), pretty=args.pretty)
        return 0
    if args.command == "review":
        _print_json(review_repository(Path(args.path)), pretty=args.pretty)
        return 0
    if args.command == "v2-mission":
        _print_json(run_v2_mission({
            "root": args.path,
            "mode": args.mode,
            "mission_type": args.mission_type,
            "changed_files": _changed_from_args(args.files, args.file_list),
            "source": args.source,
            "execution_permissions": {
                "read_only": not args.allow_write,
                "allow_network": args.allow_network,
                "allow_shell": args.allow_shell,
                "allow_write": args.allow_write,
                "allow_untrusted_code": args.allow_untrusted_code,
            },
        }), pretty=args.pretty)
        return 0
    if args.command == "app-review":
        request = load_review_request_file(args.request_file) if args.request_file else {"root": args.path, "mode": args.mode, "changed_files": _changed_from_args(args.files, args.file_list), "external_review_file": args.external_review_file, "source": "cli:app-review"}
        _print_json(handle_app_review_request(request), pretty=args.pretty)
        return 0
    if args.command == "capability-review":
        _print_json(run_capability_engine(Path(args.path), _changed_from_args(args.files, args.file_list)), pretty=args.pretty)
        return 0
    if args.command == "live-github-comments":
        _print_json(fetch_pr_comments_live(args.repository, args.pr_number, token=args.token, base_url=args.base_url).to_dict(), pretty=args.pretty)
        return 0
    if args.command == "live-github-review":
        live = fetch_pr_comments_live(args.repository, args.pr_number, token=args.token, base_url=args.base_url).to_dict()
        provider = github_comments_to_external_provider(live)
        request = {"root": args.path, "mode": args.mode, "changed_files": _changed_from_args(args.files, args.file_list), "external_providers": [provider], "source": "cli:live-github-review"}
        _print_json(handle_app_review_request(request), pretty=args.pretty)
        return 0
    if args.command == "ide-bench-contract":
        _print_json(build_ide_bench_contract(), pretty=args.pretty)
        return 0
    if args.command == "battle-tests":
        _print_json(validate_battle_fixtures(Path(args.path)), pretty=args.pretty)
        return 0
    if args.command == "battle-compare":
        result = run_battle_comparison(Path(args.fixture), token=args.token, base_url=args.base_url, match_threshold=args.match_threshold)
        _print_json(result.to_dict(), pretty=args.pretty)
        return 0
    if args.command == "boundary":
        _print_json(check_action_boundary(args.action, {"requires_write_token": args.requires_write_token, "executes_untrusted_code": args.executes_untrusted_code}), pretty=args.pretty)
        return 0
    if args.command == "visibility-policy":
        _print_json(repository_visibility_policy(is_public=not args.private), pretty=args.pretty)
        return 0
    if args.command == "verify-standard":
        _print_json(verify_repository_standard(Path(args.path)).to_dict(), pretty=args.pretty)
        return 0
    if args.command == "final-proof":
        payload = run_final_proof(Path(args.path)) if args.no_fail else assert_final_proof(Path(args.path))
        _print_json(payload, pretty=args.pretty)
        return 0
    if args.command == "proof-suite":
        payload = run_end_to_end_proof(Path(args.path)) if args.no_fail else assert_end_to_end_proof(Path(args.path))
        _print_json(payload, pretty=args.pretty)
        return 0
    if args.command == "diff-review":
        payload = review_changed_files_file(Path(args.file_list)) if args.file_list else review_changed_files(parse_changed_files_text(args.files))
        _print_json(payload, pretty=args.pretty)
        return 0
    if args.command == "collect-github-comments":
        _print_json(collect_github_comments_file(Path(args.path), repository=args.repository, pr_number=args.pr_number), pretty=args.pretty)
        return 0
    if args.command == "review-batch":
        payload = run_review_learning_batch(Path(args.path), root=Path(args.root), repository=args.repository, pr_number=args.pr_number, write_memory=args.write_memory, status=args.status, only_tags=args.tag)
        _print_json(batch_summary(payload) if args.summary_only else payload, pretty=args.pretty)
        return 0
    if args.command == "ingest-review":
        _print_json(ingest_external_review_file(Path(args.path)), pretty=args.pretty)
        return 0
    if args.command == "learn-review":
        _print_json(write_learning_candidates_to_memory(Path(args.path), root=Path(args.root), status=args.status, only_tags=args.tag), pretty=args.pretty)
        return 0
    if args.command == "memory":
        store = ReviewMemoryStore(default_memory_path(args.root))
        if args.memory_command == "add":
            record = new_memory_record(kind=args.kind, title=args.title, summary=args.summary, reason=args.reason, status=args.status, scope=args.scope, evidence=args.evidence, tags=args.tag, applies_to=args.applies_to, confidence=args.confidence)
            store.add(record)
            _print_json(record.__dict__, pretty=True)
            return 0
        if args.memory_command == "list":
            _print_json([record.__dict__ for record in store.list(status=args.status, kind=args.kind, tag=args.tag)], pretty=args.pretty)
            return 0
        if args.memory_command == "search":
            _print_json([record.__dict__ for record in store.search(args.query)], pretty=args.pretty)
            return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
