function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function parseJsonOutput(text) {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try { return JSON.parse(trimmed); } catch (_error) { return null; }
}

function collectFindings(payload) {
  if (!payload || typeof payload !== "object") return [];
  const candidates = [
    payload?.cpl_review?.findings,
    payload?.semantic_review?.findings,
    payload?.packet?.cpl_review?.findings,
    payload?.packet?.semantic_review?.findings,
    payload?.evidence?.findings,
    payload?.top_findings,
    payload?.packet?.evidence?.findings,
    payload?.review_intelligence?.ranked_findings,
    payload?.packet?.review_intelligence?.ranked_findings,
    payload?.review_verdict?.blocking_findings,
    payload?.review_verdict?.major_findings,
    payload?.review_verdict?.minor_findings,
    payload?.review_verdict?.notes,
    payload?.verdict?.blocking_findings,
    payload?.verdict?.major_findings,
    payload?.verdict?.minor_findings,
    payload?.verdict?.notes,
  ];
  const findings = candidates.flatMap((item) => Array.isArray(item) ? item : []);
  const seen = new Set();
  return findings.filter((finding) => {
    const key = JSON.stringify([
      finding?.path,
      finding?.line_start ?? finding?.line,
      finding?.line_end,
      finding?.message ?? finding?.evidence,
    ]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectActions(payload) {
  const actions = payload?.required_actions
    || payload?.verdict?.required_actions
    || payload?.packet?.verdict?.required_actions
    || payload?.next_actions
    || payload?.verification?.next_actions;
  if (Array.isArray(actions)) return actions.map((item) => typeof item === "string" ? item : JSON.stringify(item));
  const suggestion = payload?.verdict?.suggested_next_action
    || payload?.review_verdict?.suggested_next_action
    || payload?.packet?.verdict?.suggested_next_action;
  return suggestion ? [suggestion] : [];
}

function summarizePayload(payload, exitCode) {
  const verdict = payload?.verdict?.verdict
    || payload?.packet?.verdict?.verdict
    || payload?.review_verdict?.verdict
    || payload?.status
    || (exitCode === 0 ? "COMPLETED" : "FAILED");
  const status = payload?.status
    || payload?.verdict?.verdict
    || payload?.packet?.verdict?.verdict
    || payload?.review_verdict?.verdict
    || verdict;
  const findingCount = payload?.evidence?.finding_count
    ?? payload?.verdict?.finding_count
    ?? payload?.packet?.verdict?.finding_count
    ?? payload?.review_verdict?.finding_count
    ?? collectFindings(payload).length;
  const action = payload?.action
    || payload?.verdict?.suggested_next_action
    || payload?.packet?.verdict?.suggested_next_action
    || payload?.review_verdict?.suggested_next_action
    || "Review output";
  const normalized = String(verdict).toLowerCase();
  const cssClass = normalized.includes("pass") || normalized.includes("verified") || normalized.includes("completed")
    ? "pass"
    : normalized.includes("need") || normalized.includes("comment")
      ? "needs"
      : normalized.includes("block") || normalized.includes("fail") || normalized.includes("request_changes")
        ? "block"
        : "";
  return { verdict: String(verdict).toUpperCase(), status, findingCount, action, exitCode, cssClass };
}

function renderFinding(finding) {
  const severity = String(finding?.severity || "note").toLowerCase();
  const lineStart = finding?.line_start ?? finding?.line;
  const lineEnd = finding?.line_end;
  const range = lineStart ? `:${escapeHtml(String(lineStart))}${lineEnd && lineEnd !== lineStart ? `-${escapeHtml(String(lineEnd))}` : ""}` : "";
  const pathText = finding?.path ? `<div class="muted"><code>${escapeHtml(finding.path)}</code>${range}</div>` : "";
  const source = finding?.specialist || finding?.provider || finding?.capability;
  return `<article class="finding ${escapeHtml(severity)}"><div class="finding-title">${escapeHtml(String(finding?.message || finding?.evidence || "Finding"))}</div>${pathText}<div class="muted">${escapeHtml([finding?.severity, finding?.category, source].filter(Boolean).join(" / "))}</div></article>`;
}

function resultCss() {
  return `body{margin:0;color:var(--vscode-foreground);background:var(--vscode-editor-background);font-family:var(--vscode-font-family)}.shell{max-width:1100px;margin:0 auto;padding:22px}.hero,.panel,.metric{border:1px solid var(--vscode-panel-border);background:var(--vscode-sideBar-background);border-radius:8px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;padding:20px}.eyebrow{margin:0 0 6px;color:var(--vscode-textLink-foreground);text-transform:uppercase;font-size:12px;letter-spacing:.08em}h1{margin:0 0 4px;font-size:24px}.muted,.metric span{color:var(--vscode-descriptionForeground)}.badge{border:1px solid var(--vscode-panel-border);border-radius:999px;padding:7px 10px;font-weight:800}.pass{color:var(--vscode-testing-iconPassed)}.needs{color:var(--vscode-testing-iconQueued)}.block{color:var(--vscode-testing-iconFailed)}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:14px 0}.metric{padding:12px}.metric strong{display:block;font-size:18px;margin-bottom:4px}.panel{padding:16px;margin-top:14px}h2{font-size:15px;margin:0 0 12px}.finding{border:1px solid var(--vscode-panel-border);border-left:4px solid var(--vscode-focusBorder);border-radius:6px;padding:10px;margin-bottom:8px;background:var(--vscode-editor-background)}.finding.blocker{border-left-color:var(--vscode-testing-iconFailed)}.finding.major{border-left-color:var(--vscode-testing-iconQueued)}.finding-title{font-weight:700;margin-bottom:5px}code{background:var(--vscode-textCodeBlock-background);padding:1px 4px;border-radius:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.empty{color:var(--vscode-descriptionForeground);border:1px dashed var(--vscode-panel-border);border-radius:6px;padding:12px}`;
}

function renderResultHtml(title, args, payload, stdout, stderr, exitCode) {
  const summary = summarizePayload(payload, exitCode);
  const findings = collectFindings(payload).slice(0, 20);
  const actions = collectActions(payload);
  const raw = stdout.trim() || stderr.trim() || "No output captured.";
  const findingCards = findings.length ? findings.map(renderFinding).join("") : `<div class="empty">No top findings were reported.</div>`;
  const actionItems = actions.length ? actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : `<li>No required actions reported.</li>`;
  return `<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${resultCss()}</style></head><body><main class="shell"><section class="hero"><div><p class="eyebrow">Sergeant Review · Cpl Reasoning</p><h1>${escapeHtml(title)}</h1><div class="muted">${escapeHtml(args.join(" "))}</div></div><div class="badge ${summary.cssClass}">${escapeHtml(summary.verdict)}</div></section><section class="metrics"><div class="metric"><strong>${escapeHtml(String(summary.status))}</strong><span>Status</span></div><div class="metric"><strong>${escapeHtml(String(summary.findingCount))}</strong><span>Findings</span></div><div class="metric"><strong>${escapeHtml(String(summary.exitCode))}</strong><span>Exit code</span></div><div class="metric"><strong>${escapeHtml(summary.action)}</strong><span>Action</span></div></section><section class="panel"><h2>Required Actions</h2><ul>${actionItems}</ul></section><section class="panel"><h2>Top Findings</h2>${findingCards}</section><section class="panel"><details><summary>Raw Evidence</summary><pre>${escapeHtml(raw)}</pre></details></section></main></body></html>`;
}

module.exports = { collectFindings, escapeHtml, parseJsonOutput, renderResultHtml, summarizePayload };
