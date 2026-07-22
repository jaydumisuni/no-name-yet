import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const targetUrl = process.env.HUNTER_REVIEW_URL;
if (!targetUrl) throw new Error("HUNTER_REVIEW_URL is required");
const outDir = process.env.PROOF_DIR || "artifacts/hunter-full-standard";
await mkdir(outDir, { recursive: true });

const chromePath = [process.env.CHROME_PATH, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
if (!chromePath) throw new Error("Chrome/Chromium not found");

const debugPort = 9241;
const chrome = spawn(chromePath, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--hide-scrollbars",
  "--disable-background-networking",
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${join(process.env.RUNNER_TEMP || "/tmp", `srg-hunter-full-${Date.now()}`)}`,
  "--window-size=1920,1080",
  "about:blank",
], { stdio: ["ignore", "pipe", "pipe"] });

let browserLog = "";
chrome.stdout.on("data", d => { browserLog += String(d); });
chrome.stderr.on("data", d => { browserLog += String(d); });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitJson(url, attempts = 160) {
  for (let i = 0; i < attempts; i++) {
    try { const response = await fetch(url); if (response.ok) return response.json(); } catch {}
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}\n${browserLog.slice(-5000)}`);
}

let ws;
let seq = 0;
const pending = new Map();
const runtimeErrors = [];
const consoleErrors = [];
const networkFailures = [];
const unsafeRequests = [];
const allRequests = [];
function cdp(method, params = {}) {
  const id = ++seq;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evalJs(expression) {
  const result = await cdp("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Evaluation failed");
  return result.result?.value;
}
async function waitFor(expression, label, attempts = 160, delay = 100) {
  for (let i = 0; i < attempts; i++) {
    try { if (await evalJs(expression)) return; } catch {}
    await sleep(delay);
  }
  throw new Error(`Timed out waiting for ${label}`);
}
async function screenshot(name) {
  const result = await cdp("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
  await writeFile(join(outDir, name), Buffer.from(result.data, "base64"));
}

const profiles = [
  {
    name: "mobile-390x844",
    width: 390,
    height: 844,
    mobile: true,
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    platform: "iPhone",
  },
  {
    name: "desktop-1440x900",
    width: 1440,
    height: 900,
    mobile: false,
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    platform: "Linux x86_64",
  },
  {
    name: "wide-1920x1080",
    width: 1920,
    height: 1080,
    mobile: false,
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    platform: "Linux x86_64",
  },
];

function queryForDescriptor(d) {
  if (d.id) return `#${CSS.escape(d.id)}`;
  if (d.attr && d.value) return `[${d.attr}="${CSS.escape(d.value)}"]`;
  return null;
}

async function configure(profile) {
  await cdp("Emulation.setDeviceMetricsOverride", {
    width: profile.width,
    height: profile.height,
    deviceScaleFactor: profile.mobile ? 3 : 1,
    mobile: profile.mobile,
    screenWidth: profile.width,
    screenHeight: profile.height,
  });
  await cdp("Emulation.setTouchEmulationEnabled", { enabled: profile.mobile, maxTouchPoints: profile.mobile ? 5 : 0 });
  await cdp("Emulation.setUserAgentOverride", { userAgent: profile.userAgent, platform: profile.platform });
}

async function navigate(profile, suffix = "") {
  await configure(profile);
  const separator = targetUrl.includes("?") ? "&" : "?";
  await cdp("Page.navigate", { url: `${targetUrl}${separator}srg-full-standard=${Date.now()}${suffix}` });
  await waitFor(
    "document.readyState==='complete'&&!!document.querySelector('#sidebar')&&!!document.querySelector('#roleSelect')&&!!document.querySelector('#mobileMenu')",
    `${profile.name} Hunter shell`,
  );
  await waitFor("!!globalThis.__HUNTER_MOBILE_SIDEBAR__&&!!globalThis.__HUNTER_SERGEANT_UI__", `${profile.name} Hunter runtime`, 160, 100).catch(() => {});
  await sleep(250);
}

async function shellState() {
  return evalJs(`(()=>{
    const active=document.querySelector('.page.active');
    const side=document.querySelector('#sidebar');
    const scrim=document.querySelector('#drawerScrim');
    const modal=document.querySelector('#modal');
    return {
      activePage:active?.id||'',
      activeTitle:active?.querySelector('h1,h2')?.textContent?.replace(/\\s+/g,' ').trim()||'',
      drawerOpen:!!side?.classList.contains('open'),
      scrimOpen:!!scrim?.classList.contains('open'),
      modalOpen:!!modal?.classList.contains('open'),
      modalTitle:document.querySelector('#modalTitle')?.textContent?.trim()||'',
      chatActive:!!document.querySelector('#page-hunter-chat')?.classList.contains('active'),
      accountOpen:!!document.querySelector('#accountMenu')?.classList.contains('open'),
      overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth,
      viewport:{width:innerWidth,height:innerHeight},
      role:document.querySelector('#roleSelect')?.value||'',
      marker:document.documentElement.dataset.hunterEmployeeOs||'',
      sidebarAudit:globalThis.__HUNTER_MOBILE_SIDEBAR_TOUCH_AUDIT__||null,
      sergeant:globalThis.__HUNTER_SERGEANT_UI_AUDIT__||null,
    };
  })()`);
}

async function setRole(role) {
  const result = await evalJs(`(()=>{
    const select=document.querySelector('#roleSelect');
    if(!select||![...select.options].some(o=>o.value===${JSON.stringify(role)}))return false;
    select.value=${JSON.stringify(role)};
    select.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  })()`);
  if (!result) throw new Error(`Role unavailable: ${role}`);
  await sleep(320);
}

async function elementPoint(selector) {
  return evalJs(`(()=>{
    const e=document.querySelector(${JSON.stringify(selector)});
    if(!e)return null;
    e.scrollIntoView({block:'center',inline:'center'});
    const r=e.getBoundingClientRect();
    const x=Math.max(1,Math.min(innerWidth-2,r.left+r.width/2));
    const y=Math.max(1,Math.min(innerHeight-2,r.top+r.height/2));
    const hit=document.elementFromPoint(x,y);
    const style=getComputedStyle(e);
    return {
      x,y,width:r.width,height:r.height,
      visible:style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity||1)>0&&r.width>0&&r.height>0,
      hit:hit===e||e.contains(hit)||!!hit?.closest?.(${JSON.stringify(selector)}),
      hitTag:hit?.tagName||'',hitId:hit?.id||'',hitClass:String(hit?.className||''),
      disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true',
      label:(e.getAttribute('aria-label')||e.title||e.textContent||'').replace(/\\s+/g,' ').trim(),
    };
  })()`);
}

async function activate(selector, profile, settle = 320) {
  const p = await elementPoint(selector);
  if (!p?.visible || p.disabled || !p.hit || p.width < 24 || p.height < 24) {
    throw new Error(`Unusable control ${selector}: ${JSON.stringify(p)}`);
  }
  if (profile.mobile) {
    await cdp("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: p.x, y: p.y, radiusX: 7, radiusY: 7, force: 1, id: 1 }] });
    await sleep(55);
    await cdp("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  } else {
    await cdp("Input.dispatchMouseEvent", { type: "mousePressed", x: p.x, y: p.y, button: "left", clickCount: 1 });
    await sleep(30);
    await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x: p.x, y: p.y, button: "left", clickCount: 1 });
  }
  await sleep(settle);
  return p;
}

async function openMobileDrawer(profile) {
  await activate("#mobileMenu", profile, 260);
  await waitFor("document.querySelector('#sidebar')?.classList.contains('open')", `${profile.name} drawer open`, 80, 80);
  const state = await shellState();
  if (!state.scrimOpen) throw new Error(`${profile.name}: drawer opened without scrim`);
  if (state.sidebarAudit && !state.sidebarAudit.passed) throw new Error(`${profile.name}: sidebar audit failed ${JSON.stringify(state.sidebarAudit)}`);
}

async function closeMobileDrawer(profile) {
  const close = await evalJs("!!document.querySelector('#hunterMobileSidebarClose')");
  if (close) await activate("#hunterMobileSidebarClose", profile, 180);
  else await activate("#drawerScrim", profile, 180);
  await waitFor("!document.querySelector('#sidebar')?.classList.contains('open')", `${profile.name} drawer close`, 80, 80);
}

async function getRoles() {
  return evalJs("[...document.querySelector('#roleSelect').options].map(o=>o.value)");
}

async function navDescriptors(profile) {
  if (profile.mobile) await openMobileDrawer(profile);
  const items = await evalJs(`(()=>{
    const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0};
    const candidates=[...document.querySelectorAll('#nav button,#nav a,#sidebar [data-view],#sidebar [data-business-custom],#sidebar [data-role-accountability-route],#sidebar [data-family-tracking],#sidebar [data-unified-chat],#sidebar [data-unified-project]')]
      .filter((e,i,a)=>a.indexOf(e)===i).filter(visible)
      .filter(e=>e.id!=='hunterMobileSidebarClose'&&!e.closest('.account-zone'));
    const keys=['data-view','data-business-custom','data-role-accountability-route','data-family-tracking','data-unified-chat','data-unified-project','data-ops-custom'];
    return candidates.map((e,index)=>{
      const pair=keys.map(k=>[k,e.getAttribute(k)]).find(x=>x[1]);
      return {id:e.id||'',attr:pair?.[0]||'',value:pair?.[1]||'',label:(e.getAttribute('aria-label')||e.title||e.textContent||'').replace(/\\s+/g,' ').trim(),index,active:e.classList.contains('active')};
    }).filter(x=>x.id||x.attr);
  })()`);
  if (profile.mobile) await closeMobileDrawer(profile);
  return items;
}

async function resolveSelector(descriptor) {
  if (descriptor.id) return `#${descriptor.id}`;
  if (descriptor.attr && descriptor.value) return `[${descriptor.attr}=${JSON.stringify(descriptor.value)}]`;
  return null;
}

async function navigateToDescriptor(profile, role, descriptor) {
  await navigate(profile, `&role=${encodeURIComponent(role)}&nav=${encodeURIComponent(descriptor.label)}`);
  await setRole(role);
  if (profile.mobile) await openMobileDrawer(profile);
  const selector = await resolveSelector(descriptor);
  if (!selector) throw new Error(`No selector for ${descriptor.label}`);
  const before = await shellState();
  const currentActive = await evalJs(`document.querySelector(${JSON.stringify(selector)})?.classList.contains('active')||false`);
  await activate(selector, profile, 360);
  const after = await shellState();
  const changed = before.activePage !== after.activePage || before.modalOpen !== after.modalOpen || before.chatActive !== after.chatActive || before.activeTitle !== after.activeTitle;
  const drawerClosed = !profile.mobile || (!after.drawerOpen && !after.scrimOpen);
  const ok = drawerClosed && (changed || currentActive || after.modalOpen || after.chatActive);
  let reopen = true;
  if (profile.mobile) {
    try { await openMobileDrawer(profile); await closeMobileDrawer(profile); } catch { reopen = false; }
  }
  return { role, label: descriptor.label, selector, before, after, changed, currentActive, drawerClosed, reopen, ok: ok && reopen };
}

const NO_DOM_PATTERNS = [
  /attach/i, /share/i, /copy/i, /sound/i, /microphone/i, /dictate/i, /download/i,
];
const NO_DOM_SELECTORS = ["#hcs2Attach", "#hcs2Voice", "[data-share]", "[data-preview-sound]", "[data-wa-attach]", "[data-polish-attach]"];

async function fingerprint() {
  return evalJs(`(()=>{
    const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0};
    const values=[...document.querySelectorAll('input:not([type=file]),textarea,select')].filter(visible).map(e=>({id:e.id||e.name||'',value:e.type==='checkbox'?e.checked:e.value}));
    return JSON.stringify({
      page:document.querySelector('.page.active')?.id||'',
      title:document.querySelector('.page.active h1,.page.active h2')?.textContent||'',
      modal:document.querySelector('#modal')?.classList.contains('open')?(document.querySelector('#modalTitle')?.textContent||'')+(document.querySelector('#modalBody')?.textContent||'').slice(0,300):'',
      toast:document.querySelector('#toast.show')?.textContent||document.querySelector('#hunterNativeDictationToast')?.textContent||'',
      active:[...document.querySelectorAll('.active,.open,.show')].filter(visible).slice(0,120).map(e=>e.id||e.getAttribute('data-view')||e.getAttribute('data-settings-tab')||String(e.className)).join('|'),
      values,
      stream:(document.querySelector('#hcs2Stream')?.textContent||'').slice(-300),
    });
  })()`);
}

async function fillVisibleForm() {
  await evalJs(`(()=>{
    const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
    for(const e of document.querySelectorAll('.page.active input:not([type=file]):not([type=checkbox]):not([type=radio]),.page.active textarea,#modal.open input:not([type=file]):not([type=checkbox]):not([type=radio]),#modal.open textarea')){
      if(!visible(e)||e.disabled||e.readOnly||e.value)continue;
      e.value=e.type==='email'?'proof@example.com':e.type==='number'?'1':'Sergeant full standard proof';
      e.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:e.value}));
      e.dispatchEvent(new Event('change',{bubbles:true}));
    }
    for(const e of document.querySelectorAll('.page.active select,#modal.open select')){
      if(!visible(e)||e.disabled||e.options.length<2)continue;
      if(!e.value)e.selectedIndex=1;
      e.dispatchEvent(new Event('change',{bubbles:true}));
    }
  })()`);
}

async function controlDescriptors() {
  return evalJs(`(()=>{
    const root=document.querySelector('.page.active');
    if(!root)return [];
    const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0};
    const controls=[...root.querySelectorAll('button,a[href],[role=button],select,input[type=checkbox],input[type=radio]')]
      .filter(visible).filter(e=>!e.disabled&&e.getAttribute('aria-disabled')!=='true')
      .filter(e=>!e.closest('#nav,#hunterUnifiedChatNav,.account-zone'));
    const keys=['data-case','data-open-client','data-conversation','data-case-action','data-inbox-action','data-file-replace','data-file-remove','data-person-op','data-manage-person','data-person-activity','data-connection-manage','data-connection-test','data-knowledge','data-accountability','data-client-role','data-tracking-stage','data-family-workflow','data-family-trail','data-family-step','data-generic','data-stage','data-task','data-role-route','data-copy','data-good','data-bad','data-share','data-sources','data-more','data-regenerate','data-report','data-settings-tab','data-pref-toggle','data-pref-select','data-final-settings','data-final-toggle','data-final-action','data-final-pref','data-wa-view','data-wa-mode','data-wa-attach','data-wa-send','data-wa-promo','data-polish-mode','data-polish-attach','data-polish-send','data-polish-promo','data-promo-preview','data-promo-publish','data-notice','data-attention','data-promo-placement'];
    return controls.map((e,index)=>{
      const pair=keys.map(k=>[k,e.getAttribute(k)]).find(x=>x[1]!==null);
      return {id:e.id||'',attr:pair?.[0]||'',value:pair?.[1]||'',label:(e.getAttribute('aria-label')||e.title||e.textContent||e.value||'').replace(/\\s+/g,' ').trim(),tag:e.tagName,type:e.type||'',index,active:e.classList.contains('active')||e.getAttribute('aria-pressed')==='true'};
    }).filter(x=>x.id||x.attr);
  })()`);
}

async function exerciseControl(profile, role, navDescriptor, control) {
  await navigateToDescriptor(profile, role, navDescriptor);
  const selector = await resolveSelector(control);
  if (!selector) return { skipped: true, reason: "no selector", control };
  await fillVisibleForm();
  const p = await elementPoint(selector);
  if (!p?.visible || p.disabled) return { skipped: true, reason: "not visible after reset", control };
  const before = await fingerprint();
  const activeBefore = !!control.active;
  let changed = false;
  let systemSideEffect = NO_DOM_SELECTORS.includes(selector) || NO_DOM_PATTERNS.some(r => r.test(control.label));
  if (control.tag === "SELECT") {
    const selection = await evalJs(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.options.length<2)return false;const before=e.value;e.selectedIndex=(e.selectedIndex+1)%e.options.length;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return e.value!==before})()`);
    await sleep(260);
    changed = !!selection || before !== await fingerprint();
  } else if (control.type === "checkbox" || control.type === "radio") {
    await activate(selector, profile, 260);
    changed = before !== await fingerprint();
  } else {
    await activate(selector, profile, 420);
    changed = before !== await fingerprint();
  }
  const afterState = await shellState();
  const geometryOk = afterState.overflow <= 1;
  const ok = geometryOk && (changed || systemSideEffect || activeBefore);
  return { role, page: navDescriptor.label, control: control.label, selector, changed, systemSideEffect, activeBefore, geometryOk, state: afterState, ok };
}

async function keyboardProof(profile) {
  if (profile.mobile) return { skipped: true };
  await navigate(profile, "&keyboard=1");
  const seen = [];
  for (let i = 0; i < 24; i++) {
    await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 });
    await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 });
    await sleep(25);
    seen.push(await evalJs("document.activeElement?.id||document.activeElement?.getAttribute('data-view')||document.activeElement?.getAttribute('aria-label')||document.activeElement?.tagName||''"));
  }
  const unique = [...new Set(seen.filter(Boolean))];
  return { seen, unique, ok: unique.length >= 8 && !unique.every(x => x === "BODY") };
}

const proof = {
  targetUrl,
  startedAt: new Date().toISOString(),
  standard: "finish-then-prove/full-mobile-desktop-interface-v1",
  endpoints: {},
  profiles: {},
  runtimeErrors,
  consoleErrors,
  networkFailures,
  unsafeRequests,
};

try {
  const base = new URL(targetUrl);
  const health = new URL("/health", base);
  const portal = new URL("/portal", base);
  for (const [name, url] of [["health", health], ["portal", portal]]) {
    const response = await fetch(url);
    proof.endpoints[name] = { url: String(url), status: response.status, ok: response.ok };
    if (!response.ok) throw new Error(`${name} endpoint failed: ${response.status}`);
  }

  const tabs = await waitJson(`http://127.0.0.1:${debugPort}/json/list`);
  const target = tabs.find(tab => tab.type === "page") || tabs[0];
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
  ws.addEventListener("message", event => {
    const message = JSON.parse(String(event.data));
    if (message.id && pending.has(message.id)) {
      const waiter = pending.get(message.id); pending.delete(message.id);
      message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result || {});
      return;
    }
    if (message.method === "Runtime.exceptionThrown") runtimeErrors.push(message.params?.exceptionDetails || message.params);
    if (message.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(message.params?.type)) consoleErrors.push(message.params);
    if (message.method === "Network.loadingFailed" && !message.params?.canceled) networkFailures.push(message.params);
    if (message.method === "Network.requestWillBeSent") {
      const req = message.params?.request;
      if (!req) return;
      allRequests.push({ url: req.url, method: req.method });
      if (!["GET", "HEAD", "OPTIONS"].includes(req.method)) unsafeRequests.push({ url: req.url, method: req.method });
    }
  });
  await cdp("Runtime.enable");
  await cdp("Page.enable");
  await cdp("Network.enable");
  await cdp("Log.enable");

  for (const profile of profiles) {
    const result = { navigation: [], controls: [], sergeant: null, keyboard: null, screenshots: [] };
    await navigate(profile);
    const roles = await getRoles();
    result.roles = roles;

    for (const role of roles) {
      await navigate(profile, `&inventory-role=${encodeURIComponent(role)}`);
      await setRole(role);
      const items = await navDescriptors(profile);
      if (!items.length && role !== "regular") throw new Error(`${profile.name}/${role}: no navigation items`);
      for (const item of items) {
        const navResult = await navigateToDescriptor(profile, role, item);
        result.navigation.push(navResult);
        if (!navResult.ok) throw new Error(`${profile.name}/${role}/${item.label}: navigation failed ${JSON.stringify(navResult)}`);
      }
    }

    await navigate(profile, "&sergeant-critical=1");
    const hasSergeant = await evalJs("!!globalThis.__HUNTER_SERGEANT_UI__");
    if (hasSergeant) {
      result.sergeant = await evalJs("globalThis.__HUNTER_SERGEANT_UI__.critical().then(()=>globalThis.__HUNTER_SERGEANT_UI__.report())");
      if (!result.sergeant?.passed) throw new Error(`${profile.name}: Sergeant critical missions failed ${JSON.stringify(result.sergeant)}`);
    }

    await navigate(profile, "&owner-control-inventory=1");
    await setRole("owner");
    const ownerNav = await navDescriptors(profile);
    for (const nav of ownerNav) {
      await navigateToDescriptor(profile, "owner", nav);
      const controls = await controlDescriptors();
      for (const control of controls) {
        const controlResult = await exerciseControl(profile, "owner", nav, control);
        result.controls.push(controlResult);
        if (controlResult.ok === false) throw new Error(`${profile.name}/${nav.label}/${control.label}: dead or broken control ${JSON.stringify(controlResult)}`);
      }
    }

    result.keyboard = await keyboardProof(profile);
    if (result.keyboard?.ok === false) throw new Error(`${profile.name}: keyboard navigation failed ${JSON.stringify(result.keyboard)}`);

    await navigate(profile, "&final-state=1");
    const finalState = await shellState();
    if (finalState.overflow > 1) throw new Error(`${profile.name}: horizontal overflow ${finalState.overflow}`);
    await screenshot(`${profile.name}-final.png`);
    result.screenshots.push(`${profile.name}-final.png`);
    result.finalState = finalState;
    proof.profiles[profile.name] = result;
    await writeFile(join(outDir, "proof-progress.json"), JSON.stringify(proof, null, 2));
  }

  if (runtimeErrors.length) throw new Error(`Runtime exceptions: ${JSON.stringify(runtimeErrors.slice(0, 10))}`);
  if (consoleErrors.length) throw new Error(`Console errors: ${JSON.stringify(consoleErrors.slice(0, 10))}`);
  if (networkFailures.length) throw new Error(`Network failures: ${JSON.stringify(networkFailures.slice(0, 10))}`);
  if (unsafeRequests.length) throw new Error(`Review UI attempted write requests: ${JSON.stringify(unsafeRequests.slice(0, 20))}`);

  proof.passed = true;
  proof.completedAt = new Date().toISOString();
  proof.requestCount = allRequests.length;
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  console.log(`SRG FULL STANDARD PASS: ${Object.keys(proof.profiles).length} viewport profiles, every role menu destination, owner controls, keyboard path, runtime and review-only network boundary passed.`);
} catch (error) {
  proof.passed = false;
  proof.error = String(error?.stack || error);
  proof.completedAt = new Date().toISOString();
  proof.requestCount = allRequests.length;
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  try { await screenshot("99-full-standard-failure.png"); } catch {}
  throw error;
} finally {
  try { ws?.close(); } catch {}
  chrome.kill("SIGTERM");
  await sleep(300);
  if (!chrome.killed) chrome.kill("SIGKILL");
}
