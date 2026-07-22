import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const targetUrl = process.env.HUNTER_REVIEW_URL;
if (!targetUrl) throw new Error("HUNTER_REVIEW_URL is required");
const outDir = process.env.PROOF_DIR || "artifacts/hunter-mobile-voice";
await mkdir(outDir, { recursive: true });

const chromePath = [process.env.CHROME_PATH, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
if (!chromePath) throw new Error("Chrome/Chromium not found");

const debugPort = 9233;
const chrome = spawn(chromePath, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--hide-scrollbars",
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${join(process.env.RUNNER_TEMP || "/tmp", `srg-hunter-voice-${Date.now()}`)}`,
  "--window-size=390,844",
  "about:blank",
], { stdio: ["ignore", "pipe", "pipe"] });

let log = "";
chrome.stdout.on("data", d => { log += String(d); });
chrome.stderr.on("data", d => { log += String(d); });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitJson(url, attempts = 120) {
  for (let i = 0; i < attempts; i++) {
    try { const response = await fetch(url); if (response.ok) return response.json(); } catch {}
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}\n${log.slice(-4000)}`);
}

let ws;
let seq = 0;
const pending = new Map();
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
async function waitFor(expression, label, attempts = 120) {
  for (let i = 0; i < attempts; i++) {
    try { if (await evalJs(expression)) return; } catch {}
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${label}`);
}
async function point(selector) {
  return evalJs(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return null;const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return{x,y,width:r.width,height:r.height,visible:getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&r.width>0&&r.height>0,hit:h===e||!!h?.closest?.(${JSON.stringify(selector)})}})()`);
}
async function touch(selector, settle = 150) {
  const p = await point(selector);
  if (!p?.visible || !p.hit || p.width < 28 || p.height < 28) throw new Error(`Not a usable touch target: ${selector} ${JSON.stringify(p)}`);
  await cdp("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: p.x, y: p.y, radiusX: 6, radiusY: 6, force: 1, id: 1 }] });
  await sleep(45);
  await cdp("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await sleep(settle);
  return p;
}
async function screenshot(name) {
  const result = await cdp("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
  await writeFile(join(outDir, name), Buffer.from(result.data, "base64"));
}
async function voiceState(stage) {
  return evalJs(`(()=>{const layer=document.querySelector('#hunterVoiceLayer'),button=document.querySelector('#hcs2Voice'),input=document.querySelector('#hcs2Input');const r=layer?.getBoundingClientRect(),s=layer?getComputedStyle(layer):null;return{stage:${JSON.stringify(stage)},overlayVisible:!!layer&&s.display!=='none'&&s.visibility!=='hidden'&&r.width>300&&r.height>300,buttonLabel:button?.getAttribute('aria-label')||'',buttonExpanded:button?.getAttribute('aria-expanded')||'',transcript:document.querySelector('#hunterVoiceTranscript')?.textContent?.trim()||'',status:document.querySelector('#hunterVoiceStatus')?.textContent?.trim()||'',input:input?.value||'',userMessages:document.querySelectorAll('.hcs2-row.user').length,hunterMessages:document.querySelectorAll('.hcs2-row.hunter').length,latestHunterMessage:globalThis.__HUNTER_VOICE_MODE__?.latestHunterMessage?.()||'',speechEvents:globalThis.__SRG_SPEECH_EVENTS__||[],audit:globalThis.__HUNTER_VOICE_MODE_AUDIT__||null,stabilityAudit:globalThis.__HUNTER_VOICE_MODE_STABILITY_AUDIT__||null}})()`);
}

const proof = { targetUrl, viewport: { width: 390, height: 844 }, input: "real touch with deterministic browser speech fixture", stages: [], startedAt: new Date().toISOString() };
try {
  const tabs = await waitJson(`http://127.0.0.1:${debugPort}/json/list`);
  const target = tabs.find(tab => tab.type === "page") || tabs[0];
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
  ws.addEventListener("message", event => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const waiter = pending.get(message.id); pending.delete(message.id);
    message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result || {});
  });
  await cdp("Runtime.enable");
  await cdp("Page.enable");
  await cdp("Page.addScriptToEvaluateOnNewDocument", { source: `
    class SergeantSpeechRecognition {
      constructor(){this.continuous=false;this.interimResults=false;this.lang='en-ZM';}
      start(){setTimeout(()=>{this.onstart?.();setTimeout(()=>{const result=[{transcript:'list my assigned work',confidence:.99}];result.isFinal=true;this.onresult?.({resultIndex:0,results:[result]});},60);},0);}
      stop(){setTimeout(()=>this.onend?.(),0);}
    }
    globalThis.SpeechRecognition=SergeantSpeechRecognition;
    globalThis.webkitSpeechRecognition=SergeantSpeechRecognition;
    globalThis.__SRG_SPEECH_EVENTS__=[];
    const synth=globalThis.speechSynthesis;
    const instrumentedCancel=function(){globalThis.__SRG_SPEECH_EVENTS__.push({type:'cancel',at:performance.now()});};
    const instrumentedSpeak=function(utterance){globalThis.__SRG_SPEECH_EVENTS__.push({type:'speak',text:utterance.text,constructor:utterance?.constructor?.name||'',nativeType:utterance instanceof globalThis.SpeechSynthesisUtterance,at:performance.now()});utterance.onstart?.();setTimeout(()=>{globalThis.__SRG_SPEECH_EVENTS__.push({type:'end',at:performance.now()});utterance.onend?.();},60);};
    try{
      Object.defineProperty(synth,'cancel',{configurable:true,value:instrumentedCancel});
      Object.defineProperty(synth,'speak',{configurable:true,value:instrumentedSpeak});
    }catch{
      const proto=Object.getPrototypeOf(synth);
      Object.defineProperty(proto,'cancel',{configurable:true,value:instrumentedCancel});
      Object.defineProperty(proto,'speak',{configurable:true,value:instrumentedSpeak});
    }
  ` });
  await cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true, screenWidth: 390, screenHeight: 844 });
  await cdp("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
  await cdp("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1", platform: "iPhone" });
  await cdp("Page.navigate", { url: targetUrl });
  await waitFor("document.readyState==='complete'&&!!globalThis.__HUNTER_MOBILE_SIDEBAR__", "Hunter mobile runtime");

  await touch("#mobileMenu", 100);
  await waitFor("document.querySelector('#sidebar')?.classList.contains('open')", "sidebar open");
  const chatSelector = await evalJs(`(()=>{const candidates=[...document.querySelectorAll('#sidebar button,#sidebar a')];const button=candidates.find(x=>/Talk to Hunter/i.test((x.textContent||'').replace(/\s+/g,' ').trim()));if(!button)return null;button.dataset.srgVoiceChat='true';return '#sidebar [data-srg-voice-chat="true"]'})()`);
  if (!chatSelector) throw new Error("Talk to Hunter was not available from the open sidebar.");
  await touch(chatSelector, 200);
  await waitFor("document.querySelector('#page-hunter-chat')?.classList.contains('active')&&!!document.querySelector('#hcs2Voice')&&!!globalThis.__HUNTER_VOICE_MODE__", "Hunter voice composer");

  const baseline = await voiceState("chat-ready"); proof.stages.push(baseline);
  await screenshot("01-chat-voice-button.png");
  await touch("#hcs2Voice", 120);
  await waitFor("!!document.querySelector('#hunterVoiceLayer')&&/list my assigned work/i.test(document.querySelector('#hunterVoiceTranscript')?.textContent||'')", "voice transcript");
  const transcript = await voiceState("transcript-ready"); proof.stages.push(transcript);
  if (!transcript.overlayVisible) throw new Error("Voice overlay is not visibly rendered.");
  if (!/list my assigned work/i.test(transcript.transcript)) throw new Error(`Voice transcript is missing: ${transcript.transcript}`);
  if (transcript.userMessages !== baseline.userMessages) throw new Error("Voice recognition sent a message before explicit confirmation.");
  if (transcript.buttonExpanded !== "true") throw new Error("Voice button does not expose the open dialog state.");
  await screenshot("02-voice-transcript-review.png");

  await touch("#hunterVoiceUse", 160);
  await waitFor("!document.querySelector('#hunterVoiceLayer')&&document.querySelector('#hcs2Input')?.value==='list my assigned work'", "transcript placed in composer");
  const reviewed = await voiceState("use-text-only"); proof.stages.push(reviewed);
  if (reviewed.userMessages !== baseline.userMessages) throw new Error("Use text sent the message instead of returning it to the composer.");
  await screenshot("03-transcript-in-composer.png");

  await touch("#hcs2Send", 240);
  await waitFor(`document.querySelectorAll('.hcs2-row.user').length===${baseline.userMessages + 1}`, "explicit voice-derived send");
  await waitFor(`document.querySelectorAll('.hcs2-row.hunter').length>${baseline.hunterMessages}`, "Hunter reply after explicit send");
  const sent = await voiceState("explicitly-sent"); proof.stages.push(sent);
  await screenshot("04-explicit-send.png");

  await touch("#hcs2Voice", 100);
  await waitFor("!!document.querySelector('#hunterVoiceLayer')", "voice overlay reopened");
  const beforeRead = await voiceState("before-read-touch"); proof.stages.push(beforeRead);
  await touch("#hunterVoiceRead", 120);
  await sleep(240);
  const read = await voiceState("after-read-touch"); proof.stages.push(read);
  await screenshot("05-read-action-result.png");
  if (!/Reading Hunter|Finished reading/.test(read.status)) {
    throw new Error(`Read aloud did not run: ${JSON.stringify({status:read.status,latestHunterMessage:read.latestHunterMessage,speechEvents:read.speechEvents,lastAction:read.stabilityAudit?.lastAction,stability:read.stabilityAudit},null,2)}`);
  }
  if (!read.speechEvents.some(event=>event.type==='speak'&&event.nativeType===true)) throw new Error(`Read aloud did not receive a native utterance: ${JSON.stringify(read.speechEvents)}`);
  if (!read.audit?.passed || !read.stabilityAudit?.passed) throw new Error(`Hunter voice audits failed: ${JSON.stringify({voice:read.audit,stability:read.stabilityAudit})}`);

  proof.passed = true;
  proof.completedAt = new Date().toISOString();
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  console.log("SRG VOICE PASS: real touch opens Voice, transcript remains reviewable, Use text does not send, explicit Send works, and a native utterance is read aloud.");
} catch (error) {
  proof.passed = false;
  proof.error = String(error?.stack || error);
  proof.completedAt = new Date().toISOString();
  await writeFile(join(outDir, "proof.json"), JSON.stringify(proof, null, 2));
  try { await screenshot("99-failure.png"); } catch {}
  throw error;
} finally {
  try { ws?.close(); } catch {}
  chrome.kill("SIGTERM");
  await sleep(250);
  if (!chrome.killed) chrome.kill("SIGKILL");
}
