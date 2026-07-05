const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");

const ACTIONS = [
  {
    label: "Review Workspace",
    description: "Full repository verdict",
    detail: "Runs PASS / NEEDS WORK / BLOCK review on the current workspace.",
    command: "sergeant.reviewWorkspace",
    args: () => ["review", workspaceRoot(), "--pretty"],
    title: "Sergeant workspace review",
  },
  {
    label: "App Bridge Review",
    description: "App contract review",
    detail: "Runs the app-facing Sergeant review contract.",
    command: "sergeant.appReviewWorkspace",
    args: () => ["app-review", workspaceRoot(), "--pretty"],
    title: "Sergeant app bridge review",
  },
  {
    label: "Proof Suite",
    description: "End-to-end proof",
    detail: "Exercises the local proof pipeline without external reviewer dependency.",
    command: "sergeant.proofSuite",
    args: () => ["proof-suite", workspaceRoot(), "--pretty"],
    title: "Sergeant proof suite",
  },
  {
    label: "Final Proof",
    description: "Release gate",
    detail: "Runs final PASS plus verification proof.",
    command: "sergeant.finalProof",
    args: () => ["final-proof", workspaceRoot(), "--pretty"],
    title: "Sergeant final proof",
  },
  {
    label: "Verify Standard",
    description: "Evidence check",
    detail: "Checks required Sergeant verification evidence.",
    command: "sergeant.verifyStandard",
    args: () => ["verify-standard", workspaceRoot(), "--pretty"],
    title: "Sergeant standard verification",
  },
  {
    label: "Battle Tests",
    description: "Benchmark fixtures",
    detail: "Validates public pull-request benchmark fixtures.",
    command: "sergeant.battleTests",
    args: () => ["battle-tests", workspaceRoot(), "--pretty"],
    title: "Sergeant battle tests",
  },
  {
    label: "IDE Contract",
    description: "Integration contract",
    detail: "Shows the VS Code, PyCharm, JetBrains, and AI handoff contract.",
    command: "sergeant.ideBenchContract",
    args: () => ["ide-bench-contract", "--pretty"],
    title: "Sergeant IDE Bench contract",
  },
];

function pythonPath() {
  return vscode.workspace.getConfiguration("sergeant").get("pythonPath") || "python";
}

function workspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    return folders[0].uri.fsPath;
  }
  return process.cwd();
}

function runSergeant(args, title) {
  const output = vscode.window.createOutputChannel("Sergeant");
  output.clear();
  output.appendLine(`$ ${pythonPath()} sergeant.py ${args.join(" ")}`);
  output.appendLine("");

  const script = path.join(__dirname, "sergeant.py");
  const child = cp.spawn(pythonPath(), [script, ...args], {
    cwd: workspaceRoot(),
    shell: false,
  });
  let stdout = "";
  let stderr = "";

  child.stdout.on("data", (data) => {
    const text = data.toString();
    stdout += text;
    output.append(text);
  });
  child.stderr.on("data", (data) => {
    const text = data.toString();
    stderr += text;
    output.append(text);
  });
  child.on("error", (error) => {
    output.show(true);
    vscode.window.showErrorMessage(`${title} failed: ${error.message}`);
  });
  child.on("close", (code) => {
    const parsed = parseJsonOutput(stdout);
    showResultPanel(title, args, parsed, stdout, stderr, code);
    if (code === 0) {
      vscode.window.showInformationMessage(`${title} completed.`);
    } else {
      vscode.window.showErrorMessage(`${title} exited with code ${code}. See Sergeant Review panel.`);
    }
  });
}

function parseJsonOutput(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch (_error) {
    return null;
  }
}

function showResultPanel(title, args, payload, stdout, stderr, exitCode) {
  const panel = vscode.window.createWebviewPanel(
    "sergeant.reviewResult",
    "Sergeant Review",
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );
  panel.webview.html = renderResultHtml(title, args, payload, stdout, stderr, exitCode);
}

function renderResultHtml(title, args, payload, stdout, stderr, exitCode) {
  const summary = summarizePayload(payload, exitCode);
  const findings = collectFindings(payload).slice(0, 12);
  const actions = collectActions(payload);
  const raw = stdout.trim() || stderr.trim() || "No output captured.";
  const findingCards = findings.length
    ? findings.map(renderFinding).join("")
    : `<div class="empty">No top findings were reported.</div>`;
  const actionItems = actions.length
    ? actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : `<li>No required actions reported.</li>`;

  return `<!doctype html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      body {
        margin: 0;
        color: var(--vscode-foreground);
        background: var(--vscode-editor-background);
        font-family: var(--vscode-font-family);
      }
      .shell {
        max-width: 1080px;
        margin: 0 auto;
        padding: 22px;
      }
      .hero {
        border: 1px solid var(--vscode-panel-border);
        border-radius: 8px;
        padding: 18px;
        background: var(--vscode-sideBar-background);
      }
      .topline {
        display: flex;
        justify-content: space-between;
        gap: 14px;
        align-items: flex-start;
      }
      h1 {
        margin: 0 0 4px;
        font-size: 22px;
      }
      .muted {
        color: var(--vscode-descriptionForeground);
      }
      .badge {
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid var(--vscode-panel-border);
      }
      .pass { color: var(--vscode-testing-iconPassed); }
      .needs { color: var(--vscode-testing-iconQueued); }
      .block { color: var(--vscode-testing-iconFailed); }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 10px;
        margin-top: 16px;
      }
      .metric {
        border: 1px solid var(--vscode-panel-border);
        border-radius: 6px;
        padding: 10px;
        background: var(--vscode-editor-background);
      }
      .metric strong {
        display: block;
        font-size: 18px;
        margin-bottom: 3px;
      }
      h2 {
        font-size: 15px;
        margin: 22px 0 10px;
      }
      .finding {
        border: 1px solid var(--vscode-panel-border);
        border-left: 4px solid var(--vscode-focusBorder);
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 8px;
        background: var(--vscode-sideBar-background);
      }
      .finding.blocker { border-left-color: var(--vscode-testing-iconFailed); }
      .finding.major { border-left-color: var(--vscode-testing-iconQueued); }
      .finding.minor, .finding.note { border-left-color: var(--vscode-textLink-foreground); }
      .finding-title {
        font-weight: 700;
        margin-bottom: 5px;
      }
      code {
        color: var(--vscode-textPreformat-foreground);
        background: var(--vscode-textCodeBlock-background);
        padding: 1px 4px;
        border-radius: 4px;
      }
      ul {
        padding-left: 20px;
      }
      details {
        border: 1px solid var(--vscode-panel-border);
        border-radius: 6px;
        padding: 10px;
      }
      pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font-size: 12px;
      }
      .empty {
        color: var(--vscode-descriptionForeground);
        border: 1px dashed var(--vscode-panel-border);
        border-radius: 6px;
        padding: 12px;
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <div class="topline">
          <div>
            <h1>${escapeHtml(title)}</h1>
            <div class="muted">${escapeHtml(args.join(" "))}</div>
          </div>
          <div class="badge ${summary.cssClass}">${escapeHtml(summary.verdict)}</div>
        </div>
        <div class="grid">
          <div class="metric"><strong>${escapeHtml(String(summary.status))}</strong><span class="muted">Status</span></div>
          <div class="metric"><strong>${escapeHtml(String(summary.findingCount))}</strong><span class="muted">Findings</span></div>
          <div class="metric"><strong>${escapeHtml(String(summary.exitCode))}</strong><span class="muted">Exit code</span></div>
          <div class="metric"><strong>${escapeHtml(summary.action)}</strong><span class="muted">Action</span></div>
        </div>
      </section>

      <h2>Required Actions</h2>
      <ul>${actionItems}</ul>

      <h2>Top Findings</h2>
      ${findingCards}

      <h2>Raw Evidence</h2>
      <details>
        <summary>Show raw Sergeant output</summary>
        <pre>${escapeHtml(raw)}</pre>
      </details>
    </main>
  </body>
  </html>`;
}

function summarizePayload(payload, exitCode) {
  const verdict =
    payload?.verdict?.verdict ||
    payload?.review_verdict?.verdict ||
    payload?.status ||
    (exitCode === 0 ? "COMPLETED" : "FAILED");
  const status = payload?.status || payload?.verdict?.verdict || payload?.review_verdict?.verdict || verdict;
  const findingCount =
    payload?.evidence?.finding_count ??
    payload?.verdict?.finding_count ??
    payload?.review_verdict?.finding_count ??
    collectFindings(payload).length;
  const action =
    payload?.action ||
    payload?.verdict?.suggested_next_action ||
    payload?.review_verdict?.suggested_next_action ||
    "Review output";
  const normalized = String(verdict).toLowerCase();
  const cssClass = normalized.includes("pass") || normalized.includes("verified") ? "pass" :
    normalized.includes("need") ? "needs" :
    normalized.includes("block") || normalized.includes("fail") ? "block" : "";
  return { verdict: String(verdict).toUpperCase(), status, findingCount, action, exitCode, cssClass };
}

function collectFindings(payload) {
  if (!payload || typeof payload !== "object") {
    return [];
  }
  const candidates = [
    payload?.evidence?.findings,
    payload?.top_findings,
    payload?.packet?.evidence?.findings,
    payload?.review_verdict?.blocking_findings,
    payload?.review_verdict?.major_findings,
    payload?.review_verdict?.minor_findings,
    payload?.review_verdict?.notes,
    payload?.verdict?.blocking_findings,
    payload?.verdict?.major_findings,
    payload?.verdict?.minor_findings,
    payload?.verdict?.notes,
  ];
  return candidates.flatMap((item) => Array.isArray(item) ? item : []);
}

function collectActions(payload) {
  const actions = payload?.required_actions || payload?.next_actions || payload?.verification?.next_actions;
  if (Array.isArray(actions)) {
    return actions.map((item) => typeof item === "string" ? item : JSON.stringify(item));
  }
  const suggestion = payload?.verdict?.suggested_next_action || payload?.review_verdict?.suggested_next_action;
  return suggestion ? [suggestion] : [];
}

function renderFinding(finding) {
  const severity = String(finding?.severity || "note").toLowerCase();
  const pathText = finding?.path ? `<div class="muted"><code>${escapeHtml(finding.path)}</code>${finding.line ? `:${escapeHtml(String(finding.line))}` : ""}</div>` : "";
  return `<article class="finding ${escapeHtml(severity)}">
    <div class="finding-title">${escapeHtml(String(finding?.message || finding?.evidence || "Finding"))}</div>
    ${pathText}
    <div class="muted">${escapeHtml([finding?.severity, finding?.category, finding?.provider].filter(Boolean).join(" / "))}</div>
  </article>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

class SergeantActionProvider {
  getTreeItem(item) {
    const treeItem = new vscode.TreeItem(item.label, vscode.TreeItemCollapsibleState.None);
    treeItem.description = item.description;
    treeItem.tooltip = item.detail;
    treeItem.command = {
      command: item.command,
      title: item.label,
    };
    treeItem.iconPath = new vscode.ThemeIcon("shield");
    return treeItem;
  }

  getChildren() {
    return ACTIONS;
  }
}

function activate(context) {
  const provider = new SergeantActionProvider();
  context.subscriptions.push(vscode.window.registerTreeDataProvider("sergeant.actions", provider));

  for (const action of ACTIONS) {
    context.subscriptions.push(
      vscode.commands.registerCommand(action.command, () => {
        runSergeant(action.args(), action.title);
      })
    );
  }
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
