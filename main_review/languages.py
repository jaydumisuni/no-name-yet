"""Language and file-role registry for repository intelligence.

The first version is intentionally broad: language detection is cheap and gives
later AI/review layers useful context even before deep AST analyzers exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    family: str = "general"


LANGUAGES: tuple[LanguageSpec, ...] = (
    LanguageSpec("Python", (".py", ".pyw"), family="backend"),
    LanguageSpec("JavaScript", (".js", ".mjs", ".cjs", ".jsx"), family="web"),
    LanguageSpec("TypeScript", (".ts", ".tsx", ".mts", ".cts"), family="web"),
    LanguageSpec("HTML", (".html", ".htm"), family="web"),
    LanguageSpec("CSS", (".css",), family="web"),
    LanguageSpec("SCSS", (".scss", ".sass"), family="web"),
    LanguageSpec("JSON", (".json", ".jsonc"), family="data"),
    LanguageSpec("YAML", (".yml", ".yaml"), family="data"),
    LanguageSpec("TOML", (".toml",), family="data"),
    LanguageSpec("Markdown", (".md", ".mdx"), family="docs"),
    LanguageSpec("Shell", (".sh", ".bash", ".zsh"), ("bashrc", "zshrc"), family="script"),
    LanguageSpec("PowerShell", (".ps1", ".psm1", ".psd1"), family="script"),
    LanguageSpec("Dockerfile", filenames=("Dockerfile", "Containerfile"), family="infra"),
    LanguageSpec("SQL", (".sql",), family="data"),
    LanguageSpec("R", (".r", ".R", ".rmd", ".Rmd"), family="data-science"),
    LanguageSpec("Go", (".go",), family="backend"),
    LanguageSpec("Rust", (".rs",), family="systems"),
    LanguageSpec("Java", (".java",), family="backend"),
    LanguageSpec("Kotlin", (".kt", ".kts"), family="backend"),
    LanguageSpec("C", (".c", ".h"), family="systems"),
    LanguageSpec("C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"), family="systems"),
    LanguageSpec("C#", (".cs",), family="backend"),
    LanguageSpec("PHP", (".php",), family="backend"),
    LanguageSpec("Ruby", (".rb",), ("Gemfile", "Rakefile"), family="backend"),
    LanguageSpec("Swift", (".swift",), family="mobile"),
    LanguageSpec("Dart", (".dart",), family="mobile"),
    LanguageSpec("Lua", (".lua",), family="script"),
    LanguageSpec("XML", (".xml",), family="data"),
    LanguageSpec("INI", (".ini", ".cfg", ".conf"), family="config"),
)

_EXTENSION_INDEX = {
    ext.lower(): spec for spec in LANGUAGES for ext in spec.extensions
}
_FILENAME_INDEX = {
    filename.lower(): spec for spec in LANGUAGES for filename in spec.filenames
}

ROLE_BY_NAME = {
    "readme.md": "documentation",
    "license": "legal",
    "dockerfile": "infrastructure",
    "containerfile": "infrastructure",
    "package.json": "manifest",
    "pyproject.toml": "manifest",
    "requirements.txt": "manifest",
    "gemfile": "manifest",
    "cargo.toml": "manifest",
    "go.mod": "manifest",
    "pom.xml": "manifest",
    "build.gradle": "manifest",
    "settings.gradle": "manifest",
    "pubspec.yaml": "manifest",
    "renv.lock": "lockfile",
    "package-lock.json": "lockfile",
    "yarn.lock": "lockfile",
    "pnpm-lock.yaml": "lockfile",
    "poetry.lock": "lockfile",
    "cargo.lock": "lockfile",
}

RISKY_DIR_PARTS = {
    ".github",
    "workflows",
    "scripts",
    "deploy",
    "deployment",
    "infra",
    "infrastructure",
    "terraform",
    "k8s",
    "helm",
    "docker",
    "ci",
}

TEST_DIR_PARTS = {"test", "tests", "spec", "specs", "__tests__", "e2e"}
DOC_DIR_PARTS = {"doc", "docs", "documentation", "adr", "adrs"}
TEST_SUFFIXES = (
    "_test.py",
    "_test.go",
    "_test.rs",
    "_test.rb",
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
    "-test.js",
    "-test.mjs",
    "-test.cjs",
    "-test.ts",
    "-spec.js",
    "-spec.ts",
)
TEST_PREFIXES = ("test_", "test-", "spec_", "spec-")


def detect_language(path: str | Path) -> str:
    p = Path(path)
    name_key = p.name.lower()
    if name_key in _FILENAME_INDEX:
        return _FILENAME_INDEX[name_key].name
    return _EXTENSION_INDEX.get(p.suffix.lower(), LanguageSpec("Unknown")).name


def _looks_like_test_file(name_key: str) -> bool:
    return name_key.startswith(TEST_PREFIXES) or name_key.endswith(TEST_SUFFIXES)


def classify_role(path: str | Path) -> str:
    p = Path(path)
    parts = {part.lower() for part in p.parts}
    name_key = p.name.lower()

    if name_key in ROLE_BY_NAME:
        return ROLE_BY_NAME[name_key]
    if parts & TEST_DIR_PARTS or _looks_like_test_file(name_key):
        return "test"
    if parts & DOC_DIR_PARTS or p.suffix.lower() in {".md", ".mdx", ".rst"}:
        return "documentation"
    if parts & RISKY_DIR_PARTS:
        return "infrastructure"
    if p.suffix.lower() in {".env", ".key", ".pem", ".p12", ".pfx"}:
        return "sensitive"
    if p.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}:
        return "config"
    if p.suffix.lower() in {".html", ".css", ".scss", ".sass", ".jsx", ".tsx"}:
        return "ui"
    if p.suffix.lower() in {".sql"}:
        return "database"
    if detect_language(p) != "Unknown":
        return "source"
    return "unknown"


def is_high_risk_path(path: str | Path) -> bool:
    p = Path(path)
    parts = {part.lower() for part in p.parts}
    return classify_role(p) in {"sensitive", "infrastructure"} or bool(parts & RISKY_DIR_PARTS)
