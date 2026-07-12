const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { collectFindings, escapeHtml, summarizePayload } = require("./results");

class SergeantCommandCenterProvider {
  constructor(context, options) {
    this.context = context;
    this.options = options;
    this.sidebarView = null;
    this.fullPanel = null;
    this.startedAt = 0;
    this.state = {
      status: "Standing By",
      running: "",
      runningTitle: "",
      last: null,
      history: context.globalState.get("sergeant.commandCenter.history", []),
    };
  }

  resolveWebviewView(webviewView) {
    this.sidebarView = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.context.extensionPath, "resources"))],
    };
    webviewView.webview.html = this.renderCompact(webviewView.webview);
    webviewView.webview.onDidReceiveMessage((message) => this.handleMessage(message));
  }

  openFullCommandCenter() {
    if (this.fullPanel) {
      this.fullPanel.reveal(vscode.ViewColumn.One);
      this.postState();
      return;
    }
    this.fullPanel = vscode.window.createWebviewPanel(
      "sergeant.commandCenter",
      "Sergeant Command Center",
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true },
    );
    this.fullPanel.webview.html = this.renderFull();
    this.fullPanel.webview.onDidReceiveMessage((message) => this.handleMessage(message));
    this.fullPanel.onDidDispose(() => { this.fullPanel = null; });
  }

  setRunning(actionId, title) {
    this.startedAt = Date.now();
    this.state = { ...this.state, status: "Running", running: actionId || title, runningTitle: title, notice: "", error: false };
    this.postState();
  }

  setIdle(message = "") {
    this.state = { ...this.state, status: "Standing By", running: "", runningTitle: "", notice: message, error: Boolean(message) };
    this.postState();
  }

  async setResult(result) {
    const summary = summarizePayload(result.payload, result.exitCode);
    const durationSeconds = this.startedAt ? Math.max(1, Math.round((Date.now() - this.startedAt) / 1000)) : 0;
    const latest = {
      title: result.title,
      summary,
      findings: collectFindings(result.payload).slice(0, 20),
      finishedAt: result.finishedAt,
      justFinished: true,
    };
    const historyItem = {
      id: `#${String(Date.now()).slice(-6)}`,
      date: new Date(result.finishedAt).toLocaleString(),
      result: summary.verdict,
      mission: result.title,
      title: result.title,
      verdict: summary.verdict,
      duration: durationSeconds ? `${durationSeconds}s` : "—",
      finishedAt: result.finishedAt,
    };
    const history = [historyItem, ...this.state.history].slice(0, 50);
    this.state = {
      ...this.state,
      status: result.exitCode === 0 ? "Complete" : "Needs Attention",
      running: "",
      runningTitle: "",
      last: latest,
      history,
      notice: result.exitCode === 0 ? "Mission completed. Runtime evidence is available in the Evidence Locker." : `Mission exited with code ${result.exitCode}.`,
      error: result.exitCode !== 0,
    };
    await this.context.globalState.update("sergeant.commandCenter.history", history);
    await this.postState();
    this.state.last.justFinished = false;
  }

  async buildState() {
    const editor = vscode.window.activeTextEditor;
    const activeFile = editor ? path.relative(this.options.workspaceRoot(), editor.document.uri.fsPath) || editor.document.uri.fsPath : "";
    const git = await this.options.gitContext();
    return {
      ...this.state,
      platform: "VS Code",
      workspace: this.options.workspaceName(),
      workspaces: (vscode.workspace.workspaceFolders || []).map((folder) => folder.name),
      root: this.options.workspaceRoot(),
      activeFile,
      branch: git.branch,
      changedFilesCount: git.changedFilesCount,
      changedFiles: git.changedFiles,
      settings: { provider: vscode.workspace.getConfiguration("sergeant").get("provider") || "Local Model" },
    };
  }

  async postState() {
    const message = { type: "sergeantState", state: await this.buildState() };
    this.sidebarView?.webview.postMessage(message);
    this.fullPanel?.webview.postMessage(message);
  }

  async handleMessage(message) {
    try {
      if (message?.type === "run") await this.options.runAction(message.action);
      else if (message?.type === "openFull") this.openFullCommandCenter();
      else if (message?.type === "openLast") await this.options.openLast();
      else if (message?.type === "copyLast") await this.options.copyLast();
      else if (message?.type === "exportLast") await this.options.exportLast();
      else if (message?.type === "selectWorkspace") {
        this.options.selectWorkspace(String(message.workspace || ""));
        await this.postState();
      } else if (message?.type === "saveSettings") {
        if (message.settings?.provider) {
          await vscode.workspace.getConfiguration("sergeant").update("provider", message.settings.provider, vscode.ConfigurationTarget.Global);
        }
        await this.postState();
      } else if (message?.type === "refresh" || message?.type === "ready") await this.postState();
    } catch (error) {
      this.setIdle(error.message || String(error));
      vscode.window.showErrorMessage(error.message || String(error));
    }
  }

  renderCompact(webview) {
    const iconUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, "resources", "srg-logo-and-icon.png")));
    const actionButtons = this.options.actions.map((action) => `<button class="action ${action.kind === "primary" ? "primary" : ""}" data-run="${escapeHtml(action.id)}"><span>${escapeHtml(action.label)}</span><small>${escapeHtml(action.description)}</small></button>`).join("");
    return `<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>:root{--bg:#070912;--panel:#101522;--panel2:#0b0f19;--line:#334155;--text:#f8fafc;--muted:#9ca3af;--blue:#38bdf8;--purple:#a855f7}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--vscode-font-family);font-size:13px}.app{min-height:100vh}.hero{padding:16px 13px;border-bottom:1px solid var(--line);background:linear-gradient(135deg,rgba(56,189,248,.14),rgba(168,85,247,.16))}.brand{display:flex;gap:10px;align-items:center}.brand img{width:44px;height:44px;border-radius:8px}h1{margin:0;font-size:19px}.muted,small{color:var(--muted)}.status{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:12px}.tile,.panel{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:10px}.tile b{display:block}.tile span{font-size:10px;color:var(--muted);text-transform:uppercase}.tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:10px}.tabs button,.action,.open{border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:7px;padding:9px;cursor:pointer}.tabs button.active,.action.primary{border-color:var(--purple);background:rgba(168,85,247,.22)}.page{display:none;padding:0 10px 10px}.page.active{display:block}.panel{margin-bottom:8px}.grid{display:grid;gap:7px}.action{text-align:left;width:100%}.action span{display:block;font-weight:700}.open{width:100%;margin-top:10px;border-color:var(--blue);background:linear-gradient(135deg,rgba(56,189,248,.2),rgba(168,85,247,.28));font-weight:800}</style></head><body><div class="app"><header class="hero"><div class="brand"><img src="${iconUri}" alt="Sergeant"><div><h1>SGT Command Center</h1><div class="muted">Observe. Analyze. Verify.</div></div></div><div class="status"><div class="tile"><b id="statusText">Standing By</b><span>Status</span></div><div class="tile"><b id="lastText">No report</b><span>Last result</span></div></div><button class="open" id="openFull">Open Full Command Center</button></header><nav class="tabs"><button class="active" data-page="dashboard">Dashboard</button><button data-page="orders">Mission Planner</button><button data-page="reports">Evidence Locker</button></nav><section id="dashboard" class="page active"><div class="panel"><b>Review Doctrine</b><p class="muted">Evidence first. Verdict second. Nothing is assumed.</p></div><div class="panel"><b>Quick Missions</b><div class="grid">${actionButtons}</div></div></section><section id="orders" class="page"><div class="panel"><b>Mission Planner</b><p class="muted">Open the full Command Center for briefing, officers, armoury, provider selection and permissions.</p><button class="action primary" data-run="reviewWorkspace"><span>Launch Repository Review</span><small>Run live Sergeant evidence collection</small></button></div></section><section id="reports" class="page"><div class="panel"><b>Evidence Locker</b><p class="muted" id="reportTitle">No runtime report yet.</p><button class="action" id="openLast"><span>Open Last Report</span><small>Show evidence and verdict</small></button></div></section></div><script>const vscode=acquireVsCodeApi();const showPage=id=>{document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id===id));document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.page===id));};document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>showPage(b.dataset.page));document.querySelectorAll('[data-run]').forEach(b=>b.onclick=()=>vscode.postMessage({type:'run',action:b.dataset.run}));document.getElementById('openFull').onclick=()=>vscode.postMessage({type:'openFull'});document.getElementById('openLast').onclick=()=>vscode.postMessage({type:'openLast'});window.addEventListener('message',event=>{const m=event.data;if(!['state','sergeantState'].includes(m.type))return;const s=m.state||{};document.getElementById('statusText').textContent=s.running?'Running':(s.status||'Standing By');document.getElementById('lastText').textContent=s.last?s.last.summary.verdict:'No report';document.getElementById('reportTitle').textContent=s.last?(s.last.title+': '+s.last.summary.verdict):'No runtime report yet.';});vscode.postMessage({type:'ready'});</script></body></html>`;
  }

  renderFull() {
    const resourceRoot = path.join(this.context.extensionPath, "resources");
    const html = fs.readFileSync(path.join(resourceRoot, "sergeant-command-center-v2.html"), "utf8");
    const css = fs.readFileSync(path.join(resourceRoot, "sergeant-command-center-v2.css"), "utf8");
    const responsiveCss = fs.readFileSync(path.join(resourceRoot, "sergeant-command-center-v2-responsive.css"), "utf8");
    const script = fs.readFileSync(path.join(resourceRoot, "sergeant-command-center-v2.js"), "utf8");
    const bootstrap = `<script>const __sergeantVsCode=acquireVsCodeApi();window.sergeantHostSend=(payload)=>{const value=typeof payload==='string'?JSON.parse(payload):payload;__sergeantVsCode.postMessage(value);};</script>`;
    return html
      .replace("/* SERGEANT_CSS */", css)
      .replace("/* SERGEANT_RESPONSIVE_CSS */", responsiveCss)
      .replace("// SERGEANT_JS", script)
      .replace("<!-- SERGEANT_HOST_BOOTSTRAP -->", bootstrap);
  }
}

module.exports = { SergeantCommandCenterProvider };
