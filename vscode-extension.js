const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");

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
  output.show(true);
  output.clear();
  output.appendLine(`$ ${pythonPath()} sergeant.py ${args.join(" ")}`);

  const script = path.join(__dirname, "sergeant.py");
  const child = cp.spawn(pythonPath(), [script, ...args], {
    cwd: workspaceRoot(),
    shell: false,
  });

  child.stdout.on("data", (data) => output.append(data.toString()));
  child.stderr.on("data", (data) => output.append(data.toString()));
  child.on("error", (error) => {
    vscode.window.showErrorMessage(`${title} failed: ${error.message}`);
  });
  child.on("close", (code) => {
    if (code === 0) {
      vscode.window.showInformationMessage(`${title} completed.`);
    } else {
      vscode.window.showErrorMessage(`${title} exited with code ${code}. See Sergeant output.`);
    }
  });
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("sergeant.reviewWorkspace", () => {
      runSergeant(["review", workspaceRoot(), "--pretty"], "Sergeant workspace review");
    }),
    vscode.commands.registerCommand("sergeant.ideBenchContract", () => {
      runSergeant(["ide-bench-contract", "--pretty"], "Sergeant IDE Bench contract");
    })
  );
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
