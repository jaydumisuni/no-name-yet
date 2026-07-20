"""Static checks learned after transfer set 25's blind artifact was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".ex", ".scala", ".lua"}


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line(text: str, offset: int) -> int:
    return text[: max(0, offset)].count("\n") + 1


def _finding(
    *,
    officer: str,
    capability: str,
    category: str,
    severity: str,
    root_cause: str,
    path: str,
    line_start: int,
    message: str,
    evidence: str,
    falsifiers: list[str],
    verification: str,
    confidence: float,
    supporting: Iterable[str] = (),
) -> dict[str, Any]:
    primary = f"{path}:{line_start}"
    return {
        "source": "static-transfer-25-officer",
        "officer": officer,
        "capability": capability,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": primary,
        "supporting_evidence_refs": list(dict.fromkeys([primary, *supporting])),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": falsifiers,
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


_ELIXIR_GENERIC_TRANSFORM_RE = re.compile(
    r"\{\s*(?P<module>[A-Z][A-Za-z0-9_.]*)\s*,\s*:(?P<function>[a-z_][A-Za-z0-9_!?]*)\s*,\s*"
    r"\[\s*\{\s*\[\s*open_map\(\s*\)\s*\]\s*,\s*"
    r"open_map\(\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*):\s*not_set\(\s*\)\s*\)\s*\}\s*\]\s*\}",
    re.M,
)
_ELIXIR_KEY_ATTR_RE = re.compile(
    r"@(?P<attribute>[A-Za-z_][A-Za-z0-9_]*)\s+atom\(\s*\[\s*:(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*\]\s*\)"
)


def _elixir_discriminator_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    attributes = {
        match.group("field"): match.group("attribute")
        for match in _ELIXIR_KEY_ATTR_RE.finditer(text)
    }
    for spec in _ELIXIR_GENERIC_TRANSFORM_RE.finditer(text):
        module = spec.group("module")
        function = spec.group("function")
        field = spec.group("field")
        attribute = attributes.get(field)
        if attribute is None:
            continue
        handler = re.search(
            rf"defp\s+remote_apply\(\s*{re.escape(module)}\s*,\s*:{re.escape(function)}\s*,"
            rf"(?P<body>[\s\S]{{0,1800}}?)(?=\n\s*defp\s+remote_apply|\Z)",
            text[spec.end() :],
            re.M,
        )
        if handler is None:
            continue
        body = handler.group("body")
        update = re.search(
            rf"map_update\(\s*(?P<map>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*@{re.escape(attribute)}\s*,\s*"
            r"not_set\(\s*\)",
            body,
        )
        if update is None:
            continue
        variable = update.group("map")
        swallowed = re.search(
            rf"\{{\s*:error\s*,[^}}]*\}}\s*->\s*\{{\s*:ok\s*,\s*{re.escape(variable)}\s*\}}",
            body,
        )
        if swallowed is None:
            continue
        handler_absolute = spec.end() + handler.start("body")
        absolute = handler_absolute + swallowed.start()
        findings.append(
            _finding(
                officer="Engineer",
                capability="type_contract",
                category="correctness",
                severity="major",
                root_cause="required-discriminator-removal-error-accepted-as-success",
                path=path,
                line_start=_line(text, absolute),
                message=(
                    "A type-transform special case accepts failure to remove a required discriminator as a successful input."
                ),
                evidence=(
                    f"The declared `{module}.{function}` transform accepts a generic open map and promises removal of `{field}`. "
                    f"Its specialized handler calls `map_update` for that discriminator but converts the update-error branch into `{{:ok, {variable}}}`. "
                    "Inputs that do not contain the required discriminator therefore pass type checking unchanged."
                ),
                falsifiers=[
                    "Required a declared transform from an unconstrained open map to a map with a named discriminator removed.",
                    "Required the specialized handler to remove the same named discriminator.",
                    "Required the failed-removal branch to return the original map as success.",
                    "Excluded transforms whose input contract already requires the discriminator or whose failed-removal branch returns an error.",
                ],
                verification=(
                    f"Require `{field}` in the input type or validate through the canonical remote-call contract before transforming it; "
                    "test an ordinary map, a map carrying the discriminator, and a real struct value."
                ),
                confidence=0.99,
                supporting=(f"{path}:{_line(text, spec.start())}",),
            )
        )
    return findings


def _scala_repl_state_findings(path: str, text: str) -> list[dict[str, Any]]:
    if not re.search(r"case\s+class\s+State\s*\([^)]*\bobjectIndex\s*:\s*Int", text, re.S):
        return []
    if not re.search(r"\bvalIndex\s*:\s*Int", text):
        return []
    if not re.search(r"\binvalidObjectIndexes\s*:\s*Set\s*\[\s*Int\s*\]", text):
        return []
    speculative = re.search(r"\bnewRun\s*\(\s*istate\b", text)
    if speculative is None:
        return []
    failure = re.search(
        r"\.compile\s*\([^)]*\)\s*\.fold\s*\(\s*(?P<failure>displayErrors)\s*,",
        text,
        re.S,
    )
    if failure is None:
        return []
    if failure.start() < speculative.start():
        return []
    return [
        _finding(
            officer="Mechanic",
            capability="state_lifecycle",
            category="correctness",
            severity="major",
            root_cause="failed-compilation-leaves-speculative-repl-state-advanced",
            path=path,
            line_start=_line(text, failure.start("failure")),
            message=(
                "A failed compilation reports diagnostics without rolling the REPL back from its speculative per-input state."
            ),
            evidence=(
                "The REPL derives a new run state from the committed `istate` before compilation, and that state owns wrapper/value indexes plus invalid-object tracking. "
                "The compile fold uses bare `displayErrors` for failure, so the error branch returns no state derived from the pre-input snapshot and leaves speculative index progression visible to later inputs."
            ),
            falsifiers=[
                "Required explicit committed and speculative REPL state (`istate` and `newRun`).",
                "Required indexed wrapper/value state plus invalid-object tracking.",
                "Required a compile fold whose failure arm is only the diagnostic renderer.",
                "Excluded failure lambdas that return a rollback, restored snapshot, or explicitly invalidated state derived from `istate`.",
            ],
            verification=(
                "Return a state derived from the pre-input snapshot on compile failure, advancing only the identity needed to quarantine the failed wrapper; "
                "then verify the next successful result reuses the expected value index and cannot resolve definitions from the failed input."
            ),
            confidence=0.99,
            supporting=(f"{path}:{_line(text, speculative.start())}",),
        )
    ]


_LUA_KEY_FUNCTION_RE = re.compile(
    r"local\s+function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(?P<arg>[A-Za-z_][A-Za-z0-9_]*)\s*\)"
    r"(?P<body>[\s\S]{0,700}?)\n\s*end\b",
    re.M,
)


def _lua_async_registry_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key_function in _LUA_KEY_FUNCTION_RE.finditer(text):
        function_name = key_function.group("name")
        argument = key_function.group("arg")
        body = key_function.group("body")
        if not re.search(r"(?:workspace|get_workspace_id|ngx\.ctx|request[_-]?context)", body, re.I):
            continue
        table = re.search(
            rf"local\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*setmetatable\s*\(\s*\{{\s*\}}\s*,\s*\{{"
            rf"(?P<meta>[\s\S]{{0,1400}}?{re.escape(function_name)}\s*\(\s*{re.escape(argument)}\s*\)"
            rf"[\s\S]{{0,1400}}?)\}}\s*\)",
            text[key_function.end() :],
            re.M,
        )
        if table is None:
            continue
        table_name = table.group("table")
        timer_start = re.search(
            r"(?:\btimer\b|\.timer:|named_at\s*\()",
            text[key_function.end() + table.end() :],
            re.I,
        )
        if timer_start is None:
            continue
        absolute_timer = key_function.end() + table.end() + timer_start.start()
        timer_window = text[absolute_timer : absolute_timer + 2600]
        cleanup = re.search(
            rf"\b{re.escape(table_name)}\s*\[\s*{re.escape(argument)}\s*\]\s*=\s*nil",
            timer_window,
        )
        if cleanup is None:
            continue
        absolute = absolute_timer + cleanup.start()
        findings.append(
            _finding(
                officer="Mechanic",
                capability="async_lifecycle",
                category="concurrency",
                severity="blocker",
                root_cause="async-cleanup-recomputes-context-dependent-registry-key",
                path=path,
                line_start=_line(text, absolute),
                message=(
                    "Asynchronous cleanup indexes a registry through a key translator that depends on request-local context no longer available in the callback."
                ),
                evidence=(
                    f"Registry `{table_name}` hides key translation in metatable accessors using `{function_name}`, whose result depends on workspace/request context. "
                    f"The timer callback later executes `{table_name}[{argument}] = nil`; that expression recomputes the qualified key in the timer context instead of using the key captured when the entry was created. "
                    "The original entry can survive cleanup and block subsequent queue creation."
                ),
                falsifiers=[
                    "Required registry metatable accessors that transparently qualify keys.",
                    "Required the key function to depend on workspace or request-local context.",
                    "Required asynchronous/timer cleanup to use the unqualified original name.",
                    "Excluded code that computes the qualified key before scheduling and passes or stores that key for callback cleanup.",
                ],
                verification=(
                    "Compute the qualified registry key while request/workspace context is available, store it on the queued object or pass it into the callback, "
                    "and use the same explicit key for create, lookup, timer naming, and deletion."
                ),
                confidence=0.99,
                supporting=(f"{path}:{_line(text, key_function.start())}",),
            )
        )
    return findings


def run_static_transfer_25_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []

    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix == ".ex":
            findings.extend(_elixir_discriminator_findings(path, text))
        elif suffix == ".scala":
            findings.extend(_scala_repl_state_findings(path, text))
        elif suffix == ".lua":
            findings.extend(_lua_async_registry_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start") or 0),
            )
        ] = finding

    return {
        "schema_version": "sergeant.static-transfer-25-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
