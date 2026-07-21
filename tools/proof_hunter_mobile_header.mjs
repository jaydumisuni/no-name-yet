import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const targetUrl = process.env.HUNTER_REVIEW_URL;
if (!targetUrl) throw new Error("HUNTER_REVIEW_URL is required");

const outDir = process.env.PROOF_DIR || "artifacts/hunter-mobile-header";
await mkdir(outDir, { recursive: true });

const chromePath = [
  process.env.CHROME_PATH,
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean).find(existsSync);
if (!chromePath) throw new Error("Chrome/Chromium not found");

const debugPort = 9227;
const chrome = spawn(chromePath, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--hide-scrollbars",
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${join(process.env.RUNNER_TEMP || "/tmp", `srg-hunter-header-${Date.now()}`)}`,
  "--window-size=390,844",
  "about:blank",
], { stdio: ["ignore", "pipe", "pipe"] });

let chromeLog = "";
chrome.stdout.on("data", d => { chromeLog += String(d); });
chrome.stderr.on("data", d => { chromeLog += String(d); });

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitForJson(url, attempts = 120) {
  for (let i = 0; i < attempts; i++) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {}
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}\n${chromeLog.slice(-4000)}`);
}

let socket;
let nextId = 0;
const pending = new Map();
function cdp(method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const response = await cdp("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text || "Runtime evaluation failed");
  }
  return response.result?.value;
}
async function screenshot(name) {
  const result = await cdp("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await writeFile(join(outDir, name), Buffer.from(result.data, "base64"));
}
async function point(selector) {
  return evaluate(`(()=>{
    const e=document.querySelector(${JSON.stringify(selector)});
    if(!e)return null;
    const r=e.getBoundingClientRect();
    const x=r.left+r.width/2,y=r.top+r.height/2;
    const hit=document.elementFromPoint(x,y);
    return {x,y,width:r.width,height:r.height,visible:getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&r.width>0&&r.height>0,hit:hit===e||!!hit?.closest?.(${JSON.stringify(selector)})};
  })()`);
}
async function click(selector) {
  const p = await point(selector);
  if (!p?.visible || !p.hit || p.width < 28 || p.height < 28) {
    throw new Error(`Control is not a usable hit target: ${selector} ${JSON.stringify(p)}`);
  }
  await cdp("Input.dispatchMouseEvent", { type: "mousePressed", x: p.x, y: p.y, button: "left", clickCount: 1 });
  await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x: p.x, y: p.y, button: "left", clickCount: 1 });
  await sleep(220);
}
async function waitFor(expression, label, attempts = 120) {
  for (let i = 0; i < attempts; i++) {
    try {
      if (await evaluate(expression)) return;
    } catch {}
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${label}`);
}
async function snapshot(stage) {
  return evaluate(`(()=>{
    const q=s=>document.querySelector(s);
    const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0};
    const rect=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
    const overlap=(a,b)=>!!a&&!!b&&!(a.right<=b.left||a.left>=b.right||a.bottom<=b.top||a.top>=b.bottom);
    const top=q('.topbar'),bell=q('#hunterTopButton'),search=q('.top-search'),avatar=q('#topAvatar')||q('.topbar .avatar'),chatHead=q('.hcs2-head');
    const tr=rect(top),br=rect(bell),sr=rect(search),ar=rect(avatar),hr=rect(chatHead);
    const center=br?document.elementFromPoint(br.left+br.width/2,br.top+br.height/2):null;
    return {
      stage:${JSON.stringify(stage)},
      ready:document.readyState,
      url:location.href,
      activePage:q('.page.active')?.id||'',
      chatActive:!!q('#page-hunter-chat.active'),
      topbarVisible:visible(top),
      bellVisible:visible(bell),
      bellParent:bell?.parentElement?.className||'',
      bellLabel:bell?.getAttribute('aria-label')||'',
      bellHit:!!bell&&(center===bell||!!center?.closest?.('#hunterTopButton')),
      internalChatHeaderVisible:visible(chatHead),
      sidebarOpen:!!q('#sidebar.open'),
      scrimOpen:!!q('#drawerScrim.open'),
      notificationVisible:[...document.querySelectorAll('#hunterRoleAttention,#hunterAttentionPopUnified,#hunterRolePop')].some(visible),
      rects:{topbar:tr,bell:br,search:sr,avatar:ar,chatHead:hr},
      overlaps:{bellSearch:overlap(br,sr),bellAvatar:overlap(br,ar),topbarChatHeader:visible(chatHead)&&overlap(tr,hr)},
      hunterAudit:globalThis.__HUNTER_MOBILE_NOTIFICATION_HEADER_AUDIT__||null,
      srgLast:globalThis.__HUNTER_SERGEANT_UI__?.state?.last||null,
    };
  })()`);
}
function assertStage(data, { chat = false, notification = false } = {}) {
  const failures = [];
  if (!data.topbarVisible) failures.push("topbar is not visible");
  if (!data.bellVisible) failures.push("notification bell is not visible");
  if (!data.bellHit) failures.push("notification bell is not the topmost hit target");
  if (data.bellLabel !== "Needs attention") failures.push("notification bell has the wrong accessible label");
  if (data.overlaps.bellSearch) failures.push("bell overlaps search");
  if (data.overlaps.bellAvatar) failures.push("bell overlaps profile");
  if (data.overlaps.topbarChatHeader) failures.push("topbar overlaps Hunter chat header");
  if (chat && !data.chatActive) failures.push("Hunter chat did not open");
  if (chat && data.internalChatHeaderVisible) failures.push("duplicate Hunter chat header remains visible");
  if (notification && !data.notificationVisible) failures.push("notification preview did not open");
  if (data.hunterAudit && data.hunterAudit.passed === false) failures.push(`Hunter geometry audit failed: ${JSON.stringify(data.hunterAudit.checks)}`);
  if (failures.length) throw new Error(`${data.stage}: ${failures.join("; ")}\n${JSON.stringify(data, null, 2)}`);
}

const proof = { targetUrl, viewport: { width: 390, height: 844 }, stages: [], startedAt: new Date().toISOString() };
try {
  const tabs = await waitForJson(`http://127.0.0.1:${debugPort}/json/list`);
  const target = tabs.find(t => t.type === "page") || tabs[0];
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", event => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const waiter = pending.get(message.id);
    pending.delete(message.id);
    message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result || {});
  });

  await cdp("Runtime.enable");
  await cdp("Page.enable");
  await cdp("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
    screenWidth: 390,
    screenHeight: 844,
  });
  await cdp("Page.navigate", { url: targetUrl });
  await waitFor("document.readyState==='complete'", "page load");
  await waitFor("!!globalThis.__HUNTER_MOBILE_NOTIFICATION_HEADER__", "Hunter mobile header audit runtime");
  await sleep(350);

  const initial = await snapshot("employee-os");
  assertStage(initial);
  proof.stages.push(initial);
  await screenshot("01-employee-os-header.png");

  await click("#mobileMenu");
  await waitFor("document.querySelector('#sidebar')?.classList.contains('open')", "mobile sidebar open");
  const sidebar = await snapshot("sidebar-open");
  if (!sidebar.sidebarOpen || !sidebar.scrimOpen) throw new Error(`Sidebar did not open correctly: ${JSON.stringify(sidebar)}`);
  proof.stages.push(sidebar);
  await screenshot("02-sidebar-open.png");

  await waitFor("!!document.querySelector('#sidebar [data-view=\"hunter-chat\"],#sidebar [data-unified-chat]')", "Hunter chat navigation item");
  const chatSelector = await evaluate(`document.querySelector('#sidebar [data-view="hunter-chat"]')?'#sidebar [data-view="hunter-chat"]':'#sidebar [data-unified-chat]'`);
  await click(chatSelector);
  await waitFor("document.querySelector('#page-hunter-chat')?.classList.contains('active')", "Hunter chat active");
  await sleep(320);
  const chat = await snapshot("hunter-chat");
  assertStage(chat, { chat: true });
  proof.stages.push(chat);
  await screenshot("03-hunter-chat-header.png");

  await click("#hunterTopButton");
  await waitFor(`[...document.querySelectorAll('#hunterRoleAttention,#hunterAttentionPopUnified,#hunterRolePop')].some(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return !e.hidden&&s.display!=='none'&&r.width>0&&r.height>0})`, "notification preview");
  const notification = await snapshot("notification-open");
  assertStage(notification, { chat: true, notification: true });
  proof.stages.push(notification);
  await screenshot("04-notification-preview.png");

  proof.passed = true;
  proof.completedAt = new Date().toISOString();
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  console.log("SRG PASS: Hunter mobile header, chat transition, sidebar, bell and notification preview are visibly functional.");
} catch (error) {
  proof.passed = false;
  proof.error = String(error?.stack || error);
  proof.completedAt = new Date().toISOString();
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  try { await screenshot("99-failure.png"); } catch {}
  throw error;
} finally {
  try { socket?.close(); } catch {}
  chrome.kill("SIGTERM");
  await sleep(300);
  if (!chrome.killed) chrome.kill("SIGKILL");
}
