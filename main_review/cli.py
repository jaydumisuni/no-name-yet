"""Command line entrypoint for Main Review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .diff_review import parse_changed_files_text, review_changed_files, review_changed_files_file
from .evidence import collect_evidence
from .github_collector import collect_github_comments_file
from .memory import ReviewMemoryStore, default_memory_path, new_memory_record
from .memory_ingestion import write_learning_candidates_to_memory
from .review_batch import batch_summary, run_review_learning_batch
from .review_ingestion import ingest_external_review_file
from .scanner import scan_repository
from .verdict import review_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main-review")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Build a static repository intelligence packet.")
    scan_parser.add_argument("path", nargs="?", default=".", help="Repository path to scan.")
    scan_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    evidence_parser = subparsers.add_parser("evidence", help="Collect static review evidence without executing project code.")
    evidence_parser.add_argument("path", nargs="?", default=".", help="Repository path to inspect.")
    evidence_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    review_parser = subparsers.add_parser("review", help="Run static evidence collection and produce a verdict.")
    review_parser.add_argument("path", nargs="?", default=".", help="Repository path to review.")
    review_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    diff_parser = subparsers.add_parser("diff-review", help="Review a changed-file list without executing project code.")
    diff_source = diff_parser.add_mutually_exclusive_group(required=True)
    diff_source.add_argument("--files", help="Comma-separated or newline-like changed-file list.")
    diff_source.add_argument("--file-list", help="Path to a file containing changed-file names, such as git diff --name-only output.")
    diff_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    collect_parser = subparsers.add_parser("collect-github-comments", help="Normalize exported GitHub PR comments into ingestion JSON.")
    collect_parser.add_argument("path", help="JSON file containing GitHub PR comments/timeline payload.")
    collect_parser.add_argument("--repository", default="", help="Repository full name to attach when missing from comments.")
    collect_parser.add_argument("--pr-number", type=int, default=None, help="PR number to attach when missing from comments.")
    collect_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    batch_parser = subparsers.add_parser("review-batch", help="Run collect -> ingest -> optional memory write for PR comments.")
    batch_parser.add_argument("path", help="JSON file containing GitHub PR comments/timeline payload.")
    batch_parser.add_argument("--root", default=".", help="Repository root containing .main-review/memory.json.")
    batch_parser.add_argument("--repository", default="", help="Repository full name to attach when missing from comments.")
    batch_parser.add_argument("--pr-number", type=int, default=None, help="PR number to attach when missing from comments.")
    batch_parser.add_argument("--write-memory", action="store_true", help="Write learning candidates to Review Memory.")
    batch_parser.add_argument("--status", default="proposed", choices=["proposed", "verified", "superseded", "rejected"])
    batch_parser.add_argument("--tag", action="append", default=[], help="Only write candidates matching at least one tag. Can be repeated.")
    batch_parser.add_argument("--summary-only", action="store_true", help="Print compact batch summary only.")
    batch_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    ingest_parser = subparsers.add_parser("ingest-review", help="Ingest exported external reviewer comments for classification and learning.")
    ingest_parser.add_argument("path", help="JSON file containing external review comments.")
    ingest_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    learn_parser = subparsers.add_parser("learn-review", help="Write accepted external review learning candidates into Review Memory.")
    learn_parser.add_argument("path", help="JSON file containing external review comments.")
    learn_parser.add_argument("--root", default=".", help="Repository root containing .main-review/memory.json.")
    learn_parser.add_argument("--status", default="proposed", choices=["proposed", "verified", "superseded", "rejected"])
    learn_parser.add_argument("--tag", action="append", default=[], help="Only write candidates matching at least one tag. Can be repeated.")
    learn_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    memory_parser = subparsers.add_parser("memory", help="Manage review memory records.")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    add_parser = memory_subparsers.add_parser("add", help="Add a review memory record.")
    add_parser.add_argument("--root", default=".", help="Repository root containing .main-review/memory.json.")
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

    list_parser = memory_subparsers.add_parser("list", help="List review memory records.")
    list_parser.add_argument("--root", default=".")
    list_parser.add_argument("--kind")
    list_parser.add_argument("--status")
    list_parser.add_argument("--tag")
    list_parser.add_argument("--pretty", action="store_true")

    search_parser = memory_subparsers.add_parser("search", help="Search review memory records.")
    search_parser.add_argument("query")
    search_parser.add_argument("--root", default=".")
    search_parser.add_argument("--pretty", action="store_true")

    return parser


def _print_json(payload: object, *, pretty: bool = False) -> None:
    print(json.dumps(payload, indent=2 if pretty else None, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        insight = scan_repository(Path(args.path))
        _print_json(insight.to_dict(), pretty=args.pretty)
        return 0

    if args.command == "evidence":
        _print_json(collect_evidence(Path(args.path)), pretty=args.pretty)
        return 0

    if args.command == "review":
        _print_json(review_repository(Path(args.path)), pretty=args.pretty)
        return 0

    if args.command == "diff-review":
        if args.file_list:
            payload = review_changed_files_file(Path(args.file_list))
        else:
            payload = review_changed_files(parse_changed_files_text(args.files))
        _print_json(payload, pretty=args.pretty)
        return 0

    if args.command == "collect-github-comments":
        _print_json(
            collect_github_comments_file(
                Path(args.path),
                repository=args.repository,
                pr_number=args.pr_number,
            ),
            pretty=args.pretty,
        )
        return 0

    if args.command == "review-batch":
        payload = run_review_learning_batch(
            Path(args.path),
            root=Path(args.root),
            repository=args.repository,
            pr_number=args.pr_number,
            write_memory=args.write_memory,
            status=args.status,
            only_tags=args.tag,
        )
        _print_json(batch_summary(payload) if args.summary_only else payload, pretty=args.pretty)
        return 0

    if args.command == "ingest-review":
        _print_json(ingest_external_review_file(Path(args.path)), pretty=args.pretty)
        return 0

    if args.command == "learn-review":
        _print_json(
            write_learning_candidates_to_memory(
                Path(args.path),
                root=Path(args.root),
                status=args.status,
                only_tags=args.tag,
            ),
            pretty=args.pretty,
        )
        return 0

    if args.command == "memory":
        store = ReviewMemoryStore(default_memory_path(args.root))

        if args.memory_command == "add":
            record = new_memory_record(
                kind=args.kind,
                title=args.title,
                summary=args.summary,
                reason=args.reason,
                status=args.status,
                scope=args.scope,
                evidence=args.evidence,
                tags=args.tag,
                applies_to=args.applies_to,
                confidence=args.confidence,
            )
            store.add(record)
            _print_json(record.__dict__, pretty=True)
            return 0

        if args.memory_command == "list":
            records = store.list(status=args.status, kind=args.kind, tag=args.tag)
            _print_json([record.__dict__ for record in records], pretty=args.pretty)
            return 0

        if args.memory_command == "search":
            records = store.search(args.query)
            _print_json([record.__dict__ for record in records], pretty=args.pretty)
            return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
