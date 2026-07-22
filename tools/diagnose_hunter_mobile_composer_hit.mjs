import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const targetUrl=process.env.HUNTER_REVIEW_URL;
if(!targetUrl)throw new Error("HUNTER_REVIEW_URL is required");
const outDir=process.env.PROOF_DIR||"artifacts/hunter-mobile-composer-hit";
await mkdir(outDir,{recursive:true});
const chromePath=[process.env.CHROME_PATH,"/usr/bin/google-chrome","/usr/bin/google-chrome-stable","/usr/bin/chromium"].filter(Boolean).find(existsSync);
if(!chromePath)throw new Error("Chrome unavailable");
const debugPort=9241;
const chrome=spawn(chromePath,["--headless=new","--no-sandbox","--disable-gpu","--hide-scrollbars",`--remote-debugging-port=${debugPort}`,`--user-data-dir=${join(process.env.RUNNER_TEMP||"/tmp",`srg-hit-${Date.now()}`)}`,"--window-size=390,844","about:blank"],{stdio:["ignore","pipe","pipe"]});
let log="";chrome.stdout.on("data",d=>log+=String(d));chrome.stderr.on("data",d=>log+=String(d));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function waitJson(url){for(let i=0;i<120;i++){try{const r=await fetch(url);if(r.ok)return r.json()}catch{}await sleep(250)}throw new Error(`timeout ${url}\n${log.slice(-3000)}`)}
let ws,id=0;const pending=new Map();
function cdp(method,params={}){const n=++id;return new Promise((resolve,reject)=>{pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await cdp("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text||"eval failed");return r.result?.value}
async function waitFor(expression,label){for(let i=0;i<120;i++){try{if(await ev(expression))return}catch{}await sleep(100)}throw new Error(`timeout ${label}`)}
async function center(selector){return ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return null;const r=e.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2,width:r.width,height:r.height}})()`)}
async function touch(selector,settle=150){const p=await center(selector);if(!p)throw new Error(`missing ${selector}`);await cdp("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[{x:p.x,y:p.y,radiusX:6,radiusY:6,force:1,id:1}]});await sleep(45);await cdp("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});await sleep(settle)}
async function capture(stage){return ev(`(()=>{const input=document.querySelector('#hcs2Input');if(!input)return{stage:${JSON.stringify(stage)},missing:true};const r=input.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;const describe=e=>{const s=getComputedStyle(e);return{tag:e.tagName,id:e.id||'',class:String(e.className||''),pointerEvents:s.pointerEvents,position:s.position,zIndex:s.zIndex,display:s.display,visibility:s.visibility,opacity:s.opacity,rect:(()=>{const a=e.getBoundingClientRect();return{left:a.left,right:a.right,top:a.top,bottom:a.bottom,width:a.width,height:a.height}})(),html:e.outerHTML?.slice(0,280)||''}};return{stage:${JSON.stringify(stage)},active:{tag:document.activeElement?.tagName||'',id:document.activeElement?.id||'',class:String(document.activeElement?.className||'')},input:describe(input),point:{x,y},stack:document.elementsFromPoint(x,y).slice(0,12).map(describe),inputCount:document.querySelectorAll('#hcs2Input').length,boxCount:document.querySelectorAll('.hcs2-box').length,audit:globalThis.__HUNTER_CHAT_COMPOSER_RELIABILITY_AUDIT__||null}})()`)}

try{
 const tabs=await waitJson(`http://127.0.0.1:${debugPort}/json/list`),target=tabs.find(t=>t.type==='page')||tabs[0];
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
 ws.addEventListener('message',e=>{const m=JSON.parse(String(e.data));if(!m.id||!pending.has(m.id))return;const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result||{})});
 await cdp("Runtime.enable");await cdp("Page.enable");await cdp("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:3,mobile:true,screenWidth:390,screenHeight:844});await cdp("Emulation.setTouchEmulationEnabled",{enabled:true,maxTouchPoints:5});await cdp("Emulation.setUserAgentOverride",{userAgent:"Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",platform:"iPhone"});
 await cdp("Page.navigate",{url:targetUrl});await waitFor("document.readyState==='complete'&&!!globalThis.__HUNTER_MOBILE_SIDEBAR__","runtime");
 await touch('#mobileMenu',100);await waitFor("document.querySelector('#sidebar')?.classList.contains('open')","drawer");
 const selector=await ev(`(()=>{const b=[...document.querySelectorAll('#sidebar button,#sidebar a')].find(x=>/Talk to Hunter/i.test((x.textContent||'').replace(/\\s+/g,' ').trim()));if(!b)return null;b.dataset.srgHitChat='true';return '#sidebar [data-srg-hit-chat="true"]'})()`);if(!selector)throw new Error('chat control missing');
 await touch(selector,300);await waitFor("document.querySelector('#page-hunter-chat')?.classList.contains('active')&&!!document.querySelector('#hcs2Input')","chat");await sleep(300);
 const before=await capture('before-touch');await touch('#hcs2Input',500);const after=await capture('after-touch');
 const result={targetUrl,before,after,at:new Date().toISOString()};await writeFile(join(outDir,'hit-stack.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
}finally{try{ws?.close()}catch{}chrome.kill('SIGTERM');await sleep(250);if(!chrome.killed)chrome.kill('SIGKILL')}
