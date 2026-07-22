import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const targetUrl = process.env.HUNTER_REVIEW_URL;
if (!targetUrl) throw new Error("HUNTER_REVIEW_URL is required");
const outDir = process.env.PROOF_DIR || "artifacts/hunter-runtime-source";
await mkdir(outDir, { recursive: true });
const chromePath = [process.env.CHROME_PATH, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
if (!chromePath) throw new Error("Chrome/Chromium not found");

const port = 9243;
const chrome = spawn(chromePath, ["--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${port}`, `--user-data-dir=${join(process.env.RUNNER_TEMP || "/tmp", `srg-runtime-${Date.now()}`)}`, "about:blank"], { stdio: ["ignore", "pipe", "pipe"] });
let log = "";
chrome.stdout.on("data", d => { log += String(d); });
chrome.stderr.on("data", d => { log += String(d); });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitJson(url) { for (let i = 0; i < 120; i++) { try { const r = await fetch(url); if (r.ok) return r.json(); } catch {} await sleep(250); } throw new Error(log.slice(-4000)); }
let ws, id = 0;
const pending = new Map();
function cdp(method, params = {}) { const n = ++id; return new Promise((resolve, reject) => { pending.set(n, { resolve, reject }); ws.send(JSON.stringify({ id: n, method, params })); }); }
const errors = [];
try {
  const tabs = await waitJson(`http://127.0.0.1:${port}/json/list`);
  const page = tabs.find(x => x.type === "page") || tabs[0];
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
  ws.addEventListener("message", async event => {
    const m = JSON.parse(String(event.data));
    if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result || {}); return; }
    if (m.method !== "Runtime.exceptionThrown") return;
    const d = m.params?.exceptionDetails || {};
    const scriptId = d.scriptId || d.stackTrace?.callFrames?.[0]?.scriptId;
    const lineNumber = d.lineNumber ?? d.stackTrace?.callFrames?.[0]?.lineNumber ?? 0;
    const item = { description: d.exception?.description || d.text || "Runtime error", scriptId, lineNumber, columnNumber: d.columnNumber, url: d.url || d.stackTrace?.callFrames?.[0]?.url || "" };
    if (scriptId) {
      try {
        const source = await cdp("Debugger.getScriptSource", { scriptId });
        const lines = String(source.scriptSource || "").split("\n");
        item.sourceLines = lines.slice(Math.max(0, lineNumber - 5), lineNumber + 6).map((text, i) => ({ line: Math.max(0, lineNumber - 5) + i + 1, text }));
        item.scriptLength = lines.length;
      } catch (error) { item.sourceError = String(error); }
    }
    errors.push(item);
  });
  await cdp("Runtime.enable");
  await cdp("Debugger.enable");
  await cdp("Page.enable");
  await cdp("Page.navigate", { url: `${targetUrl}${targetUrl.includes("?") ? "&" : "?"}srg-runtime-source=${Date.now()}` });
  await sleep(3500);
  await writeFile(join(outDir, "runtime-source.json"), JSON.stringify({ targetUrl, errors, capturedAt: new Date().toISOString() }, null, 2));
  if (!errors.length) throw new Error("Expected runtime error was not reproduced.");
  console.log(JSON.stringify(errors, null, 2));
} finally {
  try { ws?.close(); } catch {}
  chrome.kill("SIGTERM");
  await sleep(250);
  if (!chrome.killed) chrome.kill("SIGKILL");
}
