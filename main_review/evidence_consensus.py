"""Tier 3 evidence and consensus engine for Sergeant.

External tools are evidence providers, not authorities. Sergeant normalizes their
findings, compares them with its own review intelligence, classifies each item,
and produces one final evidence-led consensus packet.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VERDICT_WEIGHT = {"BLOCK": 4, "REQUEST_CHANGES": 4, "NEEDS WORK": 3, "COMMENT": 2, "PASS": 1, "APPROVE": 1}
TRUSTED_INTERNAL = {"sergeant", "main-review", "review-intelligence", "capability-engine", "standard-engine"}

@dataclass(frozen=True)
class EvidenceFinding:
    source: str
    verdict: str
    message: str
    evidence: str
    classification: str
    confidence: float
    path: str | None = None
    category: str = "general"
    related_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def _text(value: object) -> str:
    return str(value or "").strip()

def _norm_verdict(value: object) -> str:
    raw = _text(value).upper().replace("_", " ")
    aliases = {"FIX": "NEEDS WORK", "CONSIDER": "NEEDS WORK", "APPROVE": "PASS", "COMMENT": "NEEDS WORK", "REQUEST CHANGES": "BLOCK", "MAJOR": "NEEDS WORK", "MINOR": "NEEDS WORK", "NOTE": "PASS", "BLOCKER": "BLOCK"}
    return aliases.get(raw, raw or "UNKNOWN")

def _key(message: str, path: str | None) -> tuple[str, str]:
    return (message.lower().strip(), path or "")

def _flatten_provider(provider: dict[str, Any]) -> list[dict[str, Any]]:
    source = _text(provider.get("source") or provider.get("name") or "external")
    verdict = _norm_verdict(provider.get("verdict") or provider.get("decision"))
    evidence = provider.get("evidence", [])
    if isinstance(evidence, list) and evidence:
        rows = []
        for item in evidence:
            if isinstance(item, dict):
                rows.append({"source": source, "verdict": _norm_verdict(item.get("verdict") or item.get("severity") or verdict), **item})
            else:
                rows.append({"source": source, "verdict": verdict, "message": str(item), "evidence": str(item)})
        return rows
    return [{"source": source, "verdict": verdict, "message": _text(provider.get("message") or verdict), "evidence": _text(provider.get("reason") or provider.get("evidence"))}]

def _classify(source: str, verdict: str, message: str, path: str | None, internal_keys: set[tuple[str, str]], duplicate_sources: list[str]) -> str:
    if len(duplicate_sources) > 1 or _key(message, path) in internal_keys or _key(message, None) in internal_keys:
        return "correct"
    if source.lower() in TRUSTED_INTERNAL:
        return "internal"
    if verdict in {"BLOCK", "NEEDS WORK"}:
        return "investigate"
    if verdict == "PASS":
        return "context"
    return "suggestion"

def build_evidence_consensus(internal_packet: dict[str, Any], external_providers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    intelligence = internal_packet.get("review_intelligence", {}) if isinstance(internal_packet, dict) else {}
    internal_findings = intelligence.get("ranked_findings", []) if isinstance(intelligence, dict) else []
    flattened: list[dict[str, Any]] = []
    for item in internal_findings:
        if isinstance(item, dict):
            flattened.append({"source": "sergeant", "verdict": item.get("severity", "NEEDS WORK"), **item})
    for provider in external_providers or []:
        if isinstance(provider, dict):
            flattened.extend(_flatten_provider(provider))

    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in flattened:
        message = _text(item.get("message"))
        path = item.get("path")
        by_key.setdefault(_key(message, path), []).append(item)

    internal_keys = {_key(_text(item.get("message")), item.get("path")) for item in internal_findings if isinstance(item, dict)}
    findings: list[EvidenceFinding] = []
    score = 0
    for rows in by_key.values():
        primary = rows[0]
        source = _text(primary.get("source") or "external")
        verdict = _norm_verdict(primary.get("verdict") or primary.get("severity"))
        message = _text(primary.get("message"))
        path = primary.get("path")
        sources = sorted({_text(row.get("source")) for row in rows if _text(row.get("source"))})
        classification = _classify(source, verdict, message, path, internal_keys, sources)
        confidence = float(primary.get("confidence") or 0.55)
        if len(sources) > 1:
            confidence = min(0.99, confidence + 0.1)
        if classification == "investigate":
            confidence = min(0.9, confidence + 0.05)
        score += VERDICT_WEIGHT.get(verdict, 1) * max(1, len(sources))
        findings.append(EvidenceFinding(
            source=source,
            verdict=verdict,
            message=message,
            evidence=_text(primary.get("evidence")),
            classification=classification,
            confidence=round(confidence, 2),
            path=path,
            category=_text(primary.get("category") or primary.get("capability") or "general"),
            related_sources=sources,
        ))

    findings.sort(key=lambda finding: (VERDICT_WEIGHT.get(finding.verdict, 0), finding.confidence), reverse=True)
    blocking = [finding for finding in findings if finding.verdict in {"BLOCK", "REQUEST_CHANGES"}]
    needs_work = [finding for finding in findings if finding.verdict == "NEEDS WORK"]
    final = "BLOCK" if blocking else "NEEDS WORK" if needs_work else "PASS"
    return {
        "verdict": final,
        "score": score,
        "summary": {
            "total_findings": len(findings),
            "blocking": len(blocking),
            "needs_work": len(needs_work),
            "external_sources": sorted({_text(provider.get("source") or provider.get("name") or "external") for provider in external_providers or [] if isinstance(provider, dict)}),
        },
        "classified_findings": [finding.to_dict() for finding in findings],
        "rule": "Sergeant owns the decision. External tools are witnesses whose evidence is weighed, challenged, and classified.",
    }
