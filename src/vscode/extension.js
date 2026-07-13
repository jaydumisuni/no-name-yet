const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");
const { createActions } = require("./actions");
const { parseJsonOutput, renderResultHtml } = require("./results");
const { SergeantCommandCenterProvider } = require("./command-center");

const extensionRoot = path.resolve(__dirname, "../..");
let lastResult = null;
let commandCenterProvider = null;
let selectedWorkspaceName = "";
let activeRun = null;
let outputChannel = null;

function pythonPath() {
  return vscode.workspace.getConfiguration("sergeant").get("pythonPath") || "python";
}

function workspaceFolder() {
  const folders = vscode.workspace.workspaceFolders || [];
  if (selectedWorkspaceName) {
    const selected = folders.find((folder) => folder.name === selectedWorkspaceName);
    if (selected) return selected;
  }
  return folders[0] || null;
}

function workspaceRoot() {
  return workspaceFolder()?.uri.fsPath || process.cwd();
}

function workspaceName() {
  return workspaceFolder()?.name || path.basename(workspaceRoot()) || "workspace";
}

async function activeRelativeFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) throw new Error("Open a file before running Review Current File.");
  return path.relative(workspaceRoot(), editor.document.uri.fsPath) || editor.document.uri.fsPath;
}

function execFile(command, args, cwd) {
  return new Promise((resolve) => cp.execFile(command, args, { cwd }, (error, stdout, stderr) => resolve({ error, stdout, stderr })));
}

async function gitContext() {
  const cwd = workspaceRoot();
  const [branchResult, changedResult] = await Promise.all([
    execFile("git", ["rev-parse", "--abbrev-ref", "HEAD"], cwd),
    execFile("git", ["status", "--porcelain"], cwd),
  ]);
  const changedFiles = changedResult.stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return {
    branch: branchResult.stdout.trim() || "not-git",
    changedFilesCount: changedFiles.length,
    changedFiles: changedFiles.map((line) => line.replace(/^..\s*/, "")),
  };
}

async function changedFilesCsv() {
  const { stdout } = await execFile("git", ["diff", "--name-only", "HEAD"], workspaceRoot());
  const files = stdout.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  if (files.length) return files.join(",");
  const editor = vscode.window.activeTextEditor;
  if (editor) return path.relative(workspaceRoot(), editor.document.uri.fsPath) || editor.document.uri.fsPath;
  throw new Error("No changed files were found in this workspace.");
}

const ACTIONS = createActions({ workspaceRoot, activeRelativeFile, changedFilesCsv });

async function actionArgs(action) {
  const value = action.args();
  return Array.isArray(value) ? value : await value;
}

async function runAction(actionId) {
  const action = ACTIONS.find((item) => item.id === actionId || item.command === actionId);
  if (!action) throw new Error(`Unknown Sergeant action: ${actionId}`);
  if (activeRun) {
    vscode.window.showWarningMessage(`${activeRun.title} is already running. Wait for its verdict before launching another Sergeant mission.`);
    return null;
  }
  return runSergeant(await actionArgs(action), action.title, action.id);
}

function clearActiveRun(child) {
  if (activeRun?.child === child) activeRun = null;
}

function runSergeant(args, title, actionId = "") {
  if (activeRun) {
    vscode.window.showWarningMessage(`${activeRun.title} is already running.`);
    return null;
  }

  const output = outputChannel || vscode.window.createOutputChannel("Sergeant");
  outputChannel = output;
  output.clear();
  output.appendLine(`$ ${pythonPath()} sergeant.py ${args.join(" ")}`);
  output.appendLine("");
  commandCenterProvider?.setRunning(actionId, title);

  const child = cp.spawn(pythonPath(), [path.join(extensionRoot, "sergeant.py"), ...args], { cwd: workspaceRoot(), shell: false });
  activeRun = { child, title, actionId };
  let stdout = "";
  let stderr = "";
  let settled = false;

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
    if (settled) return;
    settled = true;
    clearActiveRun(child);
    output.show(true);
    commandCenterProvider?.setIdle(error.message);
    vscode.window.showErrorMessage(`${title} failed: ${error.message}`);
  });
  child.on("close", async (code) => {
    if (settled) return;
    settled = true;
    clearActiveRun(child);
    const payload = parseJsonOutput(stdout);
    lastResult = { title, actionId, args, payload, stdout, stderr, exitCode: code, finishedAt: new Date().toISOString() };
    await commandCenterProvider?.setResult(lastResult);
    showResultPanel(title, args, payload, stdout, stderr, code);
    if (code === 0) vscode.window.showInformationMessage(`${title} completed.`);
    else vscode.window.showErrorMessage(`${title} exited with code ${code}. See Sergeant Review panel.`);
  });
  return child;
}

function showResultPanel(title, args, payload, stdout, stderr, exitCode) {
  const panel = vscode.window.createWebviewPanel("sergeant.reviewResult", "Sergeant Review", vscode.ViewColumn.Beside, { enableScripts: true });
  panel.webview.html = renderResultHtml(title, args, payload, stdout, stderr, exitCode);
}

async function openLastReport() {
  if (!lastResult) return vscode.window.showInformationMessage("No Sergeant report is available yet.");
  showResultPanel(lastResult.title, lastResult.args, lastResult.payload, lastResult.stdout, lastResult.stderr, lastResult.exitCode);
}

async function copyLastReport() {
  if (!lastResult) return vscode.window.showInformationMessage("No Sergeant report is available to copy.");
  await vscode.env.clipboard.writeText(lastResult.stdout || JSON.stringify(lastResult.payload, null, 2));
  vscode.window.showInformationMessage("Sergeant report copied.");
}

async function exportLastReport() {
  if (!lastResult) return vscode.window.showInformationMessage("No Sergeant report is available to export.");
  const target = await vscode.window.showSaveDialog({
    defaultUri: vscode.Uri.file(path.join(workspaceRoot(), "sergeant-report.json")),
    filters: { JSON: ["json"], Text: ["txt"] },
  });
  if (!target) return;
  const body = lastResult.stdout || JSON.stringify(lastResult.payload, null, 2);
  await vscode.workspace.fs.writeFile(target, Buffer.from(body, "utf8"));
  vscode.window.showInformationMessage(`Sergeant report exported to ${target.fsPath}`);
}

function activate(context) {
  outputChannel = vscode.window.createOutputChannel("Sergeant");
  context.subscriptions.push(outputChannel);
  commandCenterProvider = new SergeantCommandCenterProvider(context, {
    actions: ACTIONS,
    workspaceRoot,
    workspaceName,
    gitContext,
    runAction,
    openLast: openLastReport,
    copyLast: copyLastReport,
    exportLast: exportLastReport,
    selectWorkspace: (name) => { selectedWorkspaceName = name; },
  });
  context.subscriptions.push(vscode.window.registerWebviewViewProvider("sergeant.actions", commandCenterProvider));
  for (const action of ACTIONS) context.subscriptions.push(vscode.commands.registerCommand(action.command, () => runAction(action.id)));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.openCommandCenter", () => commandCenterProvider.openFullCommandCenter()));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.openLastReport", openLastReport));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.copyLastReport", copyLastReport));
  context.subscriptions.push(vscode.commands.registerCommand("sergeant.exportLastReport", exportLastReport));
}

function deactivate() {
  if (activeRun?.child && !activeRun.child.killed) activeRun.child.kill();
  activeRun = null;
}

module.exports = { activate, deactivate };
