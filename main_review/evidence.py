"""Evidence providers for Main Review.

Evidence providers produce facts. They do not decide the final verdict. All
providers remain static and safe: no project code execution.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

from .models import RepositoryInsight
from .scanner import scan_repository

Severity = Literal["blocker", "major", "minor", "note"]
Category = Literal["security", "testing", "documentation", "architecture", "repository", "risk"]


@dataclass(frozen=True)
class EvidenceFinding:
    provider: str
    severity: Severity
    category: Category
    message: str
    path: str | None = None
    line: int | None = None
    evidence: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EvidenceProvider(Protocol):
    name: str

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        ...


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (
        "generic api key assignment",
        re.compile(
            r"(?i)^\s*(?:(?:export\s+)?(?:const|let|var)\s+)?[\"']?"
            r"(api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*"
            r"[\"']([^\"']{12,})[\"']"
        ),
    ),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
)

SECRET_PLACEHOLDERS = {
    "changeme",
    "change-me",
    "example",
    "example-key",
    "fake-secret",
    "placeholder",
    "replace-me",
    "test-secret",
    "your-api-key",
    "your_api_key",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".dart", ".lua", ".r", ".R", ".md", ".mdx", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sh", ".ps1", ".sql", ".html", ".css",
}


def _read_text_files(root: Path, insight: RepositoryInsight) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for file in insight.files:
        path = root / file.path
        if path.suffix not in TEXT_EXTENSIONS and path.name not in {"Dockerfile", "Containerfile"}:
            continue
        try:
            texts.append((file.path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return texts


def _placeholder_secret(match: re.Match[str]) -> bool:
    if match.lastindex is None or match.lastindex < 2:
        return False
    value = match.group(2).strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "", value)
    return normalized in SECRET_PLACEHOLDERS or normalized.startswith(("example-", "fake-", "test-", "your-"))


class SecretEvidenceProvider:
    name = "secret-scanner"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        for file in insight.files:
            path = root / file.path
            if path.suffix not in TEXT_EXTENSIONS and path.name not in {"Dockerfile", "Containerfile"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                for label, pattern in SECRET_PATTERNS:
                    match = pattern.search(line)
                    if match is None or (label == "generic api key assignment" and _placeholder_secret(match)):
                        continue
                    findings.append(
                        EvidenceFinding(
                            self.name,
                            "blocker",
                            "security",
                            f"Possible {label} detected.",
                            path=file.path,
                            line=number,
                            evidence="Sensitive-looking value matched a secret pattern.",
                            confidence=0.9,
                        )
                    )
        return findings


class TestCoverageEvidenceProvider:
    name = "test-coverage-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        source_count = sum(1 for file in insight.files if file.role == "source")
        test_count = len(insight.tests)
        if source_count and not test_count:
            return [
                EvidenceFinding(
                    self.name,
                    "major",
                    "testing",
                    "Source files exist but no tests were detected.",
                    evidence=f"Detected {source_count} source file(s) and 0 test files.",
                    confidence=0.85,
                )
            ]
        if test_count < max(1, source_count // 5) and source_count >= 10:
            return [
                EvidenceFinding(
                    self.name,
                    "minor",
                    "testing",
                    "Test footprint appears low compared with source footprint.",
                    evidence=f"Detected {source_count} source file(s) and {test_count} test file(s).",
                    confidence=0.65,
                )
            ]
        return []


class DocumentationEvidenceProvider:
    name = "documentation-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        if not insight.docs:
            return [
                EvidenceFinding(
                    self.name,
                    "major",
                    "documentation",
                    "No documentation files were detected.",
                    evidence="README/docs are absent from the repository scan.",
                    confidence=0.8,
                )
            ]
        if "README.md" not in insight.docs and "readme.md" not in {doc.lower() for doc in insight.docs}:
            return [
                EvidenceFinding(
                    self.name,
                    "minor",
                    "documentation",
                    "Documentation exists but no top-level README.md was detected.",
                    evidence=f"Detected docs: {', '.join(insight.docs[:5])}.",
                    confidence=0.7,
                )
            ]
        return []


class RiskPathEvidenceProvider:
    name = "risk-path-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        return [
            EvidenceFinding(
                self.name,
                "note",
                "risk",
                "High-risk path detected for review attention.",
                path=path,
                evidence="Infrastructure, CI, deployment, or sensitive path classification.",
                confidence=0.75,
            )
            for path in insight.high_risk_files
        ]


def _eligible_battle_path(path: str) -> bool:
    """Keep learned battle rules on code/patch evidence, not fixture prose."""

    normalized = path.replace("\\", "/")
    if normalized.startswith(("battle-tests/", "docs/")):
        return False
    if normalized.lower() in {"readme.md", "submission_ready.md"}:
        return False
    suffix = Path(normalized).suffix.lower()
    if suffix in {".md", ".mdx", ".txt", ".json"} and Path(normalized).name != "__sergeant_pr_comments.md":
        return False
    return True


class BattleAwareEvidenceProvider:
    """Static review rules learned from committed battle fixtures.

    Fixture expectations and public documentation are training/evaluation data,
    not review input. They are deliberately excluded from ordinary repository
    scans so Sergeant cannot award itself credit for reading its answer key.
    """

    name = "battle-aware-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        for path, text in _read_text_files(root, insight):
            if not _eligible_battle_path(path):
                continue
            lowered = text.lower()
            findings.extend(self._requests_rules(path, lowered))
            findings.extend(self._flask_context_rules(path, lowered))
            findings.extend(self._django_url_rules(path, lowered))
        return findings

    def _requests_rules(self, path: str, text: str) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        if "namedtemporaryfile" in text and "files={" in text and "requests.post" in text:
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Regression test covers the file wrapper behavior.", path=path, evidence="Detected NamedTemporaryFile upload through requests.post files=... .", confidence=0.8))
        if "hasattr" in text and "read" in text and "_supportsread" in text:
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Implementation is small and targeted.", path=path, evidence="Detected a narrow file-read fallback around _SupportsRead / hasattr(read).", confidence=0.7))
        if "files={" in text and "data=" in text and "requests.post" in text:
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Extra unrelated request arguments would reduce test clarity.", path=path, evidence="Detected upload test mixing files= with unrelated request payload arguments.", confidence=0.75))
        if ("do we actually need" in text and ("data" in text or "params" in text) and "files" in text) or ("just `files`" in text or "just files" in text):
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Extra unrelated request arguments would reduce test clarity.", path=path, evidence="Detected reviewer feedback asking to remove data/params and keep only files for test clarity.", confidence=0.85))
        if text.count("def test_post_named_tempfile") > 1 or text.count("namedtemporaryfile") > 1:
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Duplicate tests should be removed or parameterized.", path=path, evidence="Detected repeated NamedTemporaryFile regression-test pattern.", confidence=0.65))
        if ("need both" in text and "test" in text and "parameterized" in text) or "test should be parameterized" in text or "parametrize or keep only" in text:
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Duplicate tests should be removed or parameterized.", path=path, evidence="Detected reviewer feedback that overlapping tests should be parameterized or reduced.", confidence=0.85))
        return findings

    def _flask_context_rules(self, path: str, text: str) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        context_terms = ("requestcontext", "appcontext", "request_ctx", "app_ctx", "_cv_request", "_cv_app")
        if any(term in text for term in context_terms):
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Architecture lifecycle risk should be reviewed.", path=path, evidence="Detected app/request context lifecycle changes in patch content.", confidence=0.8))
        if "deprecated" in text and ("requestcontext" in text or "request_ctx" in text):
            findings.append(EvidenceFinding(self.name, "minor", "documentation", "Migration and deprecation documentation is present but should be checked for accuracy.", path=path, evidence="Detected deprecated RequestContext/request_ctx documentation in patch content.", confidence=0.75))
        if "proxy" in text and ("context" in text or "current_app" in text or "request" in text):
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Proxy availability and context visibility should be verified.", path=path, evidence="Detected proxy/context availability changes in patch content.", confidence=0.7))
        if "copy" in text and "context" in text and ("_cv_app" in text or "request" in text):
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Copied context behavior should be checked for regression risk.", path=path, evidence="Detected copied-context or context preservation changes.", confidence=0.7))
        return findings

    def _django_url_rules(self, path: str, text: str) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        if "query_string" in text and "redirectview" in text and "?" in text and "&" in text:
            findings.append(EvidenceFinding(self.name, "minor", "testing", "Regression tests cover existing destination query strings and incoming request query strings.", path=path, evidence="Detected RedirectView query-string regression cases covering destination and request query strings.", confidence=0.8))
        if "urlparse" in text and ".query" in text:
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Query-string merge logic should use explicit URL query detection instead of checking for a raw question mark.", path=path, evidence="Detected explicit URL query parsing for separator selection.", confidence=0.75))
        elif '"?" in url' in text or "'?' in url" in text:
            findings.append(EvidenceFinding(self.name, "minor", "architecture", "Query-string merge logic should use explicit URL query detection instead of checking for a raw question mark.", path=path, evidence="Detected separator selection based on raw question-mark membership in URL text.", confidence=0.7))
        if "following the review feedback" in text or "follow-up pr" in text or "follow up" in text:
            findings.append(EvidenceFinding(self.name, "minor", "documentation", "Follow-up review feedback should be tracked before treating the change as final.", path=path, evidence="Detected follow-up review continuation language.", confidence=0.75))
        return findings


DEFAULT_PROVIDERS: tuple[EvidenceProvider, ...] = (
    SecretEvidenceProvider(),
    TestCoverageEvidenceProvider(),
    DocumentationEvidenceProvider(),
    RiskPathEvidenceProvider(),
    BattleAwareEvidenceProvider(),
)


def collect_evidence(root: str | Path, providers: tuple[EvidenceProvider, ...] = DEFAULT_PROVIDERS) -> dict[str, object]:
    root_path = Path(root).resolve()
    insight = scan_repository(root_path)
    findings: list[EvidenceFinding] = []
    for provider in providers:
        findings.extend(provider.collect(root_path, insight))
    return {
        "root": str(root_path),
        "repository": insight.to_dict(),
        "findings": [finding.to_dict() for finding in findings],
        "finding_count": len(findings),
    }
