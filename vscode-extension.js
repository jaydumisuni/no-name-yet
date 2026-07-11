const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");

let lastResult = null;
let commandCenterProvider = null;

const ACTIONS = [
  {
    id: "reviewWorkspace",
    label: "Review Workspace",
    description: "Full repository verdict",
    command: "sergeant.reviewWorkspace",
    title: "Sergeant workspace review",
    args: () => ["review", workspaceRoot(), "--pretty"],
    page: "orders",
    kind: "primary",
  },
  {
    id: "appReviewWorkspace",
    label: "App Bridge Review",
    description: "App contract review",
    command: "sergeant.appReviewWorkspace",
    title: "Sergeant app bridge review",
    args: () => ["app-review", workspaceRoot(), "--pretty"],
    page: "orders",
  },
  {
    id: "reviewCurrentFile",
    label: "Review Current File",
    description: "Changed-file review",
    command: "sergeant.reviewCurrentFile",
    title: "Sergeant current file review",
    args: async () => ["app-review", workspaceRoot(), "--mode", "changed_files", "--files", await activeRelativeFile(), "--pretty"],
    page: "orders",
  },
  {
    id: "reviewChangedFiles",
    label: "Review Changed Files",
    description: "Git changed files",
    command: "sergeant.reviewChangedFiles",
    title: "Sergeant changed files review",
    args: async () => ["app-review", workspaceRoot(), "--mode", "changed_files", "--files", await changedFilesCsv(), "--pretty"],
    page: "orders",
  },
  {
    id: "v2Mission",
    label: "V2 Mission",
    description: "Mission briefing",
    command: "sergeant.v2Mission",
    title: "Sergeant V2 mission",
    args: () => ["v2-mission", workspaceRoot(), "--mission-type", "release_gate_review", "--pretty"],
    page: "orders",
  },
  {
    id: "proofSuite",
    label: "Proof Suite",
    description: "End-to-end proof",
    command: "sergeant.proofSuite",
    title: "Sergeant proof suite",
    args: () => ["proof-suite", workspaceRoot(), "--pretty"],
    page: "proof",
  },
  {
    id: "finalProof",
    label: "Final Proof",
    description: "Release gate",
    command: "sergeant.finalProof",
    title: "Sergeant final proof",
    args: () => ["final-proof", workspaceRoot(), "--pretty"],
    page: "proof",
    kind: "primary",
  },
  {
    id: "verifyStandard",
    label: "Verify Standard",
    description: "Evidence check",
    command: "sergeant.verifyStandard",
    title: "Sergeant standard verification",
    args: () => ["verify-standard", workspaceRoot(), "--pretty"],
    page: "proof",
  },
  {
    id: "battleTests",
    label: "Battle Tests",
    description: "Benchmark fixtures",
    command: "sergeant.battleTests",
    title: "Sergeant battle tests",
    args: () => ["battle-tests", workspaceRoot(), "--pretty"],
    page: "proof",
  },
  {
    id: "ideBenchContract",
    label: "IDE Contract",
    description: "Integration contract",
    command: "sergeant.ideBenchContract",
    title: "Sergeant IDE Bench contract",
    args: () => ["ide-bench-contract", "--pretty"],
    page: "doctrine",
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

async function activeRelativeFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    throw new Error("Open a file before running Review Current File.");
  }
  return path.relative(workspaceRoot(), editor.document.uri.fsPath) || editor.document.uri.fsPath;
}

function execFile(command, args, cwd) {
  return new Promise((resolve) => {
    cp.execFile(command, args, { cwd }, (error, stdout, stderr) => {
      resolve({ error, stdout, stderr });
    });
  });
}

async function changedFilesCsv() {
  const cwd = workspaceRoot();
  const { stdout } = await execFile("git", ["diff", "--name-only", "HEAD"], cwd);
  const files = stdout.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  if (!files.length) {
    const editor = vscode.window.activeTextEditor;
    if (editor) {
      return path.relative(cwd, editor.document.uri.fsPath) || editor.document.uri.fsPath;
    }
    throw new Error("No changed files were found in this workspace.");
  }
  return files.join(",");
}

async function actionArgs(action) {
  const value = action.args();
  return Array.isArray(value) ? value : await value;
}

async function runAction(actionId) {
  const action = ACTIONS.find((item) => item.id === actionId || item.command === actionId);
  if (!action) {
    throw new Error(`Unknown Sergeant action: ${actionId}`);
  }
  const args = await actionArgs(action);
  return runSergeant(args, action.title, action.id);
}

function runSergeant(args, title, actionId = "") {
  const output = vscode.window.createOutputChannel("Sergeant");
  output.clear();
  output.appendLine(`$ ${pythonPath()} sergeant.py ${args.join(" ")}`);
  output.appendLine("");
  commandCenterProvider?.setRunning(actionId, title);

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
    commandCenterProvider?.setIdle();
    vscode.window.showErrorMessage(`${title} failed: ${error.message}`);
  });
  child.on("close", (code) => {
    const parsed = parseJsonOutput(stdout);
    lastResult = { title, args, payload: parsed, stdout, stderr, exitCode: code, finishedAt: new Date().toISOString() };
    commandCenterProvider?.setResult(lastResult);
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
    { enableScripts: true }
  );
  panel.webview.html = renderResultHtml(title, args, payload, stdout, stderr, exitCode);
}

function renderResultHtml(title, args, payload, stdout, stderr, exitCode) {
  const summary = summarizePayload(payload, exitCode);
  const findings = collectFindings(payload).slice(0, 14);
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
    <style>${resultCss()}</style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Sergeant Review</p>
          <h1>${escapeHtml(title)}</h1>
          <div class="muted">${escapeHtml(args.join(" "))}</div>
        </div>
        <div class="badge ${summary.cssClass}">${escapeHtml(summary.verdict)}</div>
      </section>
      <section class="metrics">
        <div class="metric"><strong>${escapeHtml(String(summary.status))}</strong><span>Status</span></div>
        <div class="metric"><strong>${escapeHtml(String(summary.findingCount))}</strong><span>Findings</span></div>
        <div class="metric"><strong>${escapeHtml(String(summary.exitCode))}</strong><span>Exit code</span></div>
        <div class="metric"><strong>${escapeHtml(summary.action)}</strong><span>Action</span></div>
      </section>
      <section class="panel">
        <h2>Required Actions</h2>
        <ul>${actionItems}</ul>
      </section>
      <section class="panel">
        <h2>Top Findings</h2>
        ${findingCards}
      </section>
      <section class="panel">
        <details>
          <summary>Raw Evidence</summary>
          <pre>${escapeHtml(raw)}</pre>
        </details>
      </section>
    </main>
  </body>
  </html>`;
}

function resultCss() {
  return `
    body{margin:0;color:var(--vscode-foreground);background:var(--vscode-editor-background);font-family:var(--vscode-font-family)}
    .shell{max-width:1100px;margin:0 auto;padding:22px}
    .hero,.panel,.metric{border:1px solid var(--vscode-panel-border);background:var(--vscode-sideBar-background);border-radius:8px}
    .hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;padding:20px}
    .eyebrow{margin:0 0 6px;color:var(--vscode-textLink-foreground);text-transform:uppercase;font-size:12px;letter-spacing:.08em}
    h1{margin:0 0 4px;font-size:24px}.muted,.metric span{color:var(--vscode-descriptionForeground)}
    .badge{border:1px solid var(--vscode-panel-border);border-radius:999px;padding:7px 10px;font-weight:800}.pass{color:var(--vscode-testing-iconPassed)}.needs{color:var(--vscode-testing-iconQueued)}.block{color:var(--vscode-testing-iconFailed)}
    .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:14px 0}.metric{padding:12px}.metric strong{display:block;font-size:18px;margin-bottom:4px}
    .panel{padding:16px;margin-top:14px}h2{font-size:15px;margin:0 0 12px}
    .finding{border:1px solid var(--vscode-panel-border);border-left:4px solid var(--vscode-focusBorder);border-radius:6px;padding:10px;margin-bottom:8px;background:var(--vscode-editor-background)}
    .finding.blocker{border-left-color:var(--vscode-testing-iconFailed)}.finding.major{border-left-color:var(--vscode-testing-iconQueued)}.finding-title{font-weight:700;margin-bottom:5px}
    code{background:var(--vscode-textCodeBlock-background);padding:1px 4px;border-radius:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.empty{color:var(--vscode-descriptionForeground);border:1px dashed var(--vscode-panel-border);border-radius:6px;padding:12px}
  `;
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
  const cssClass = normalized.includes("pass") || normalized.includes("verified") || normalized.includes("completed") ? "pass" :
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

class SergeantCommandCenterProvider {
  constructor(context) {
    this.context = context;
    this.view = null;
    this.state = { status: "Standing By", running: "", last: null };
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.context.extensionPath, "resources"))],
    };
    webviewView.webview.html = this.render(webviewView.webview);
    webviewView.webview.onDidReceiveMessage((message) => this.handleMessage(message));
  }

  setRunning(actionId, title) {
    this.state = { ...this.state, status: "Running", running: actionId || title };
    this.postState();
  }

  setIdle() {
    this.state = { ...this.state, status: "Standing By", running: "" };
    this.postState();
  }

  setResult(result) {
    const summary = summarizePayload(result.payload, result.exitCode);
    this.state = { status: result.exitCode === 0 ? "Complete" : "Needs Attention", running: "", last: { title: result.title, summary, finishedAt: result.finishedAt } };
    this.postState();
  }

  postState() {
    this.view?.webview.postMessage({ type: "state", state: this.state });
  }

  async handleMessage(message) {
    try {
      if (message?.type === "run") {
        await runAction(message.action);
      } else if (message?.type === "openLast") {
        if (lastResult) {
          showResultPanel(lastResult.title, lastResult.args, lastResult.payload, lastResult.stdout, lastResult.stderr, lastResult.exitCode);
        } else {
          vscode.window.showInformationMessage("No Sergeant report is available yet.");
        }
      } else if (message?.type === "copyLast") {
        await copyLastReport();
      } else if (message?.type === "exportLast") {
        await exportLastReport();
      } else if (message?.type === "refresh") {
        this.postState();
      }
    } catch (error) {
      this.setIdle();
      vscode.window.showErrorMessage(error.message || String(error));
    }
  }

  render(webview) {
    const iconUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, "resources", "srg-logo-and-icon.png")));
    return renderCommandCenterHtml(iconUri);
  }
}

async function copyLastReport() {
  if (!lastResult) {
    vscode.window.showInformationMessage("No Sergeant report is available to copy.");
    return;
  }
  await vscode.env.clipboard.writeText(lastResult.stdout || JSON.stringify(lastResult.payload, null, 2));
  vscode.window.showInformationMessage("Sergeant report copied.");
}

async function exportLastReport() {
  if (!lastResult) {
    vscode.window.showInformationMessage("No Sergeant report is available to export.");
    return;
  }
  const target = await vscode.window.showSaveDialog({
    defaultUri: vscode.Uri.file(path.join(workspaceRoot(), "sergeant-report.json")),
    filters: { "JSON": ["json"], "Text": ["txt"] },
  });
  if (!target) {
    return;
  }
  const body = lastResult.stdout || JSON.stringify(lastResult.payload, null, 2);
  await vscode.workspace.fs.writeFile(target, Buffer.from(body, "utf8"));
  vscode.window.showInformationMessage(`Sergeant report exported to ${target.fsPath}`);
}

function renderCommandCenterHtml(iconUri) {
  const actionButtons = ACTIONS.map((action) => `
    <button class="action ${action.kind === "primary" ? "primary" : ""}" data-run="${escapeHtml(action.id)}">
      <span>${escapeHtml(action.label)}</span>
      <small>${escapeHtml(action.description)}</small>
    </button>
  `).join("");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  :root{--bg:#070912;--panel:#101522;--panel2:#0b0f19;--line:#334155;--text:#f8fafc;--muted:#9ca3af;--blue:#38bdf8;--purple:#a855f7;--green:#22c55e;--yellow:#eab308;--red:#ef4444}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--vscode-font-family);font-size:13px}
  .app{min-height:100vh;display:flex;flex-direction:column}.hero{padding:18px 14px 14px;border-bottom:1px solid var(--line);background:linear-gradient(135deg,rgba(56,189,248,.14),rgba(168,85,247,.16))}
  .brand{display:flex;gap:12px;align-items:center}.brand img{width:48px;height:48px;border-radius:9px;border:1px solid rgba(168,85,247,.65)}h1{margin:0;font-size:22px;letter-spacing:.02em}.subtitle{margin-top:3px;color:var(--muted)}
  .status{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.tile{border:1px solid var(--line);background:rgba(7,9,18,.72);border-radius:8px;padding:9px}.tile b{display:block;font-size:15px}.tile span{color:var(--muted);font-size:11px;text-transform:uppercase}
  .tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:10px 10px 0}.tabs button{border:1px solid var(--line);background:var(--panel2);color:var(--muted);border-radius:7px;padding:8px 6px;white-space:normal;cursor:pointer;min-height:34px}.tabs button.active{color:white;border-color:var(--purple);background:rgba(168,85,247,.22)}
  .page{display:none;padding:12px}.page.active{display:block}.panel{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:12px;margin-bottom:10px}h2{font-size:15px;margin:0 0 9px}.muted{color:var(--muted)}.grid{display:grid;gap:8px}.action{width:100%;border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:8px;padding:10px;text-align:left;cursor:pointer}.action:hover{border-color:var(--blue)}.action.primary{border-color:var(--purple);background:linear-gradient(135deg,rgba(168,85,247,.28),rgba(56,189,248,.12))}.action span{display:block;font-weight:700}.action small{display:block;color:var(--muted);margin-top:3px}
  .mission{display:grid;gap:8px}select,input{width:100%;background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:7px;padding:8px}.checks{display:grid;grid-template-columns:1fr 1fr;gap:7px}.checks label{border:1px solid var(--line);background:var(--panel2);border-radius:7px;padding:8px}
  .summary{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid rgba(148,163,184,.22);padding:7px 0}.summary:last-child{border-bottom:0}.pass{color:var(--green)}.work{color:var(--yellow)}.block{color:var(--red)}.blue{color:var(--blue)}
  .officers{display:grid;grid-template-columns:1fr 1fr;gap:8px}.officer{border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:10px}.officer b{color:#d8b4fe}.footer{margin-top:auto;padding:10px 12px;border-top:1px solid var(--line);display:flex;gap:8px}.footer button{flex:1;border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:7px;padding:8px;cursor:pointer}
</style>
</head>
<body>
<div class="app">
  <header class="hero">
    <div class="brand">
      <img src="${iconUri}" alt="Sergeant">
      <div><h1>SGT Command Center</h1><div class="subtitle">Observe. Analyze. Verify.</div></div>
    </div>
    <div class="status">
      <div class="tile"><b id="statusText">Standing By</b><span>Status</span></div>
      <div class="tile"><b id="lastText">No report</b><span>Last result</span></div>
    </div>
  </header>
  <nav class="tabs">
    <button class="active" data-page="dashboard">Dashboard</button>
    <button data-page="orders">Missions</button>
    <button data-page="proof">Proof</button>
    <button data-page="reports">Reports</button>
    <button data-page="doctrine">Doctrine</button>
    <button data-page="settings">Settings</button>
  </nav>
  <section id="dashboard" class="page active">
    <div class="panel"><h2>Commander</h2><p class="muted">Sergeant commands. Specialists advise. Evidence decides.</p><div class="summary"><span>Mode</span><b class="pass">Read-only default</b></div><div class="summary"><span>Contract</span><b class="blue">V1 stable + V2 packet</b></div><div class="summary"><span>Release</span><b>v2</b></div></div>
    <div class="panel"><h2>Quick Actions</h2><div class="grid">${actionButtons}</div></div>
  </section>
  <section id="orders" class="page">
    <div class="panel mission"><h2>Mission Planner</h2><label>Mission Type<select id="missionType"><option value="reviewWorkspace">Repository Review</option><option value="appReviewWorkspace">App Bridge Review</option><option value="reviewCurrentFile">Current File Review</option><option value="reviewChangedFiles">Changed Files Review</option><option value="v2Mission">V2 Release Gate Mission</option></select></label><label>Briefing<input id="briefing" value="Review workspace evidence."></label><div class="checks"><label><input type="checkbox" checked> Static evidence</label><label><input type="checkbox" checked> Docs check</label><label><input type="checkbox" checked> Proof gate</label><label><input type="checkbox"> External review</label></div><button class="action primary" id="launchMission"><span>Launch Mission</span><small>Run selected Sergeant command</small></button></div>
  </section>
  <section id="proof" class="page"><div class="panel"><h2>Proof Gates</h2><button class="action primary" data-run="finalProof"><span>Final Proof</span><small>Release gate</small></button><button class="action" data-run="proofSuite"><span>Proof Suite</span><small>End-to-end proof</small></button><button class="action" data-run="verifyStandard"><span>Verify Standard</span><small>Evidence checklist</small></button><button class="action" data-run="battleTests"><span>Battle Tests</span><small>Benchmark fixtures</small></button></div></section>
  <section id="reports" class="page"><div class="panel"><h2>Evidence Locker</h2><div class="summary"><span>Last command</span><b id="reportTitle">None</b></div><div class="summary"><span>Verdict</span><b id="reportVerdict">Waiting</b></div><div class="summary"><span>Finished</span><b id="reportTime">-</b></div></div><div class="panel"><button class="action" id="openLast"><span>Open Last Report</span><small>Show the latest result panel</small></button><button class="action" id="copyLast"><span>Copy Last Report</span><small>Copy raw JSON/text to clipboard</small></button><button class="action" id="exportLast"><span>Export Last Report</span><small>Save report to disk</small></button></div></section>
  <section id="doctrine" class="page"><div class="panel"><h2>Review Doctrine</h2><div class="summary"><span>1</span><b>Finish, then prove</b></div><div class="summary"><span>2</span><b>Code should justify execution</b></div><div class="summary"><span>3</span><b>Claims must match implementation</b></div><div class="summary"><span>4</span><b>Evidence before conclusions</b></div><div class="summary"><span>5</span><b>Tests are proof, not discovery</b></div></div><div class="panel"><h2>Officers</h2><div class="officers"><div class="officer"><b>Scout</b><p class="muted">Discovery</p></div><div class="officer"><b>Engineer</b><p class="muted">Architecture</p></div><div class="officer"><b>Medic</b><p class="muted">Safety</p></div><div class="officer"><b>Judge</b><p class="muted">Verdict</p></div></div></div><div class="panel"><button class="action" data-run="ideBenchContract"><span>Show IDE Contract</span><small>Validate integration contract</small></button></div></section>
  <section id="settings" class="page"><div class="panel"><h2>Settings</h2><div class="summary"><span>Python</span><b>sergeant.pythonPath</b></div><div class="summary"><span>Execution</span><b class="pass">No untrusted code by default</b></div><div class="summary"><span>Writes</span><b class="block">Human approval required</b></div></div></section>
  <footer class="footer"><button id="refresh">Refresh</button><button data-page-button="reports">Reports</button></footer>
</div>
<script>
  const vscode = acquireVsCodeApi();
  function showPage(id){document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id===id));document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.page===id));}
  document.querySelectorAll('[data-page]').forEach(btn=>btn.addEventListener('click',()=>showPage(btn.dataset.page)));
  document.querySelectorAll('[data-page-button]').forEach(btn=>btn.addEventListener('click',()=>showPage(btn.dataset.pageButton)));
  document.querySelectorAll('[data-run]').forEach(btn=>btn.addEventListener('click',()=>vscode.postMessage({type:'run',action:btn.dataset.run})));
  document.getElementById('launchMission').addEventListener('click',()=>vscode.postMessage({type:'run',action:document.getElementById('missionType').value}));
  document.getElementById('openLast').addEventListener('click',()=>vscode.postMessage({type:'openLast'}));
  document.getElementById('copyLast').addEventListener('click',()=>vscode.postMessage({type:'copyLast'}));
  document.getElementById('exportLast').addEventListener('click',()=>vscode.postMessage({type:'exportLast'}));
  document.getElementById('refresh').addEventListener('click',()=>vscode.postMessage({type:'refresh'}));
  window.addEventListener('message',(event)=>{const msg=event.data;if(msg.type!=='state')return;const s=msg.state||{};document.getElementById('statusText').textContent=s.running?'Running':(s.status||'Standing By');document.getElementById('lastText').textContent=s.last?s.last.summary.verdict:'No report';document.getElementById('reportTitle').textContent=s.last?s.last.title:'None';document.getElementById('reportVerdict').textContent=s.last?s.last.summary.verdict:'Waiting';document.getElementById('reportTime').textContent=s.last?new Date(s.last.finishedAt).toLocaleString():'-';});
  vscode.postMessage({type:'refresh'});
</script>
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function activate(context) {
  commandCenterProvider = new SergeantCommandCenterProvider(context);
  context.subscriptions.push(vscode.window.registerWebviewViewProvider("sergeant.actions", commandCenterProvider));

  for (const action of ACTIONS) {
    context.subscriptions.push(
      vscode.commands.registerCommand(action.command, () => runAction(action.id))
    );
  }
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.openLastReport", () => commandCenterProvider.handleMessage({ type: "openLast" })));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.copyLastReport", () => commandCenterProvider.handleMessage({ type: "copyLast" })));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.exportLastReport", () => commandCenterProvider.handleMessage({ type: "exportLast" })));
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
