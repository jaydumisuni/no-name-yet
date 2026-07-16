from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected source block not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "main_review/cloudflare_cli.py",
        "import json\nimport shlex\n",
        "import json\nimport re\nimport shlex\n",
    )
    replace_once(
        "main_review/cloudflare_cli.py",
        '''def _proof_contract_matches(payload: dict[str, Any], model: str) -> bool:\n    candidates = [payload]\n    for key in ("required", "result"):\n        nested = payload.get(key)\n        if isinstance(nested, dict):\n            candidates.append(nested)\n    return any(\n        candidate.get("status") == "ready"\n        and candidate.get("model") == model\n        and candidate.get("capabilities") == REQUIRED_PROOF_CAPABILITIES\n        for candidate in candidates\n    )\n''',
        '''def _proof_contract_matches(payload: dict[str, Any], model: str) -> bool:\n    candidates = [payload]\n    result = payload.get("result")\n    if isinstance(result, dict):\n        candidates.append(result)\n    return any(\n        candidate.get("status") == "ready"\n        and candidate.get("model") == model\n        and candidate.get("capabilities") == REQUIRED_PROOF_CAPABILITIES\n        for candidate in candidates\n    )\n''',
    )
    replace_once(
        "main_review/cloudflare_cli.py",
        '''_SECURITY_COVERAGE_MARKERS = (\n    "security",\n    "injection",\n    "shell",\n    "auth",\n    "authorization",\n    "trust boundary",\n    "vulnerability",\n    "remote code execution",\n    "rce",\n)\n\n\ndef _coverage_area_matches(expected_category: str, reviewed_areas: set[str]) -> bool:\n    expected = expected_category.strip().lower()\n    if not expected:\n        return True\n    if expected in reviewed_areas:\n        return True\n    if expected == "security":\n        return any(\n            marker in area\n            for area in reviewed_areas\n            for marker in _SECURITY_COVERAGE_MARKERS\n        )\n    return False\n''',
        '''_SECURITY_COVERAGE_PATTERNS = tuple(\n    re.compile(pattern)\n    for pattern in (\n        r"\\bsecurity\\b",\n        r"\\binjection\\b",\n        r"\\bshell(?:[ _-]+execution)?\\b",\n        r"\\bauthentication\\b",\n        r"\\bauthorization\\b",\n        r"\\btrust[ _-]+boundar(?:y|ies)\\b",\n        r"\\bvulnerabilit(?:y|ies)\\b",\n        r"\\bremote[ _-]+code[ _-]+execution\\b",\n        r"\\brce\\b",\n    )\n)\n\n\ndef _coverage_area_matches(expected_category: str, reviewed_areas: set[str]) -> bool:\n    expected = expected_category.strip().lower()\n    if not expected:\n        return True\n    if expected in reviewed_areas:\n        return True\n    if expected == "security":\n        return any(\n            pattern.search(area)\n            for area in reviewed_areas\n            for pattern in _SECURITY_COVERAGE_PATTERNS\n        )\n    return False\n''',
    )

    replace_once(
        "main_review/llm_provider.py",
        '''    return bool(\n        "http 429" in message\n        or "code 4006" in message\n        or '\"code\":4006' in message\n        or "daily free allocation" in message\n        or "quota circuit is open" in message\n    )\n''',
        '''    return bool(\n        "code 4006" in message\n        or '\"code\":4006' in message\n        or "daily free allocation" in message\n        or "daily allocation is exhausted" in message\n        or "quota circuit is open" in message\n    )\n''',
    )
    replace_once(
        "main_review/llm_provider.py",
        '''def _json_candidate_score(payload: dict[str, Any]) -> tuple[int, int]:\n    keys = {str(key) for key in payload}\n    important = {"verdict", "findings", "coverage", "status", "model", "capabilities"}\n    score = len(keys & important) * 10\n    required = payload.get("required")\n    if isinstance(required, dict):\n        score += len({str(key) for key in required} & important) * 8\n    return score, len(json.dumps(payload, sort_keys=True, default=str))\n''',
        '''def _json_candidate_score(payload: dict[str, Any]) -> int:\n    keys = {str(key) for key in payload}\n    important = {"verdict", "findings", "coverage", "status", "model", "capabilities"}\n    return len(keys & important) * 10\n''',
    )
    replace_once(
        "main_review/llm_provider.py",
        '''        objects: list[dict[str, Any]] = []\n        for index, character in enumerate(candidate):\n            if character != "{":\n                continue\n            try:\n                value, _ = decoder.raw_decode(candidate[index:])\n            except json.JSONDecodeError:\n                continue\n            if isinstance(value, dict):\n                objects.append(value)\n        if not objects:\n            raise LLMProviderError("Cpl model output did not contain a parseable JSON object.") from None\n        payload = max(objects, key=_json_candidate_score)\n''',
        '''        objects: list[tuple[int, dict[str, Any]]] = []\n        for index, character in enumerate(candidate):\n            if character != "{":\n                continue\n            try:\n                value, _ = decoder.raw_decode(candidate[index:])\n            except json.JSONDecodeError:\n                continue\n            if isinstance(value, dict):\n                objects.append((index, value))\n        if not objects:\n            raise LLMProviderError("Cpl model output did not contain a parseable JSON object.") from None\n        payload = max(\n            objects,\n            key=lambda item: (_json_candidate_score(item[1]), item[0]),\n        )[1]\n''',
    )


if __name__ == "__main__":
    main()
