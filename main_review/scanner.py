"""Repository scanner for Main Review.

This is intentionally static: it walks files, classifies language/role/risk, and
builds a context packet without executing project code.
"""

from __future__ import annotations

import os
from pathlib import Path

from .languages import classify_role, detect_language, is_high_risk_path
from .models import FileInsight, RepositoryInsight

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}


def scan_repository(root: str | Path, *, ignore_dirs: set[str] | None = None) -> RepositoryInsight:
    root_path = Path(root).resolve()
    ignored = DEFAULT_IGNORE_DIRS | (ignore_dirs or set())
    insight = RepositoryInsight(root=str(root_path))

    for current_root, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in ignored]
        for filename in filenames:
            absolute = Path(current_root) / filename
            relative = absolute.relative_to(root_path).as_posix()
            language = detect_language(relative)
            role = classify_role(relative)
            high_risk = is_high_risk_path(relative)
            file_insight = FileInsight(
                path=relative,
                language=language,
                role=role,
                high_risk=high_risk,
            )
            insight.files.append(file_insight)
            insight.languages[language] = insight.languages.get(language, 0) + 1
            insight.roles[role] = insight.roles.get(role, 0) + 1

            if high_risk:
                insight.high_risk_files.append(relative)
            if role == "documentation":
                insight.docs.append(relative)
            if role == "test":
                insight.tests.append(relative)
            if role == "manifest":
                insight.manifests.append(relative)

    insight.files.sort(key=lambda item: item.path)
    return insight
