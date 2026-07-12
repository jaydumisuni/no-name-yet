(() => {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const missionMap = {
    "Repository Review": "reviewWorkspace",
    "Pull Request Review": "reviewChangedFiles",
    "Release Verification": "finalProof",
    "Battle Comparison": "battleTests",
    "Final Proof": "finalProof",
    "IDE Review": "ideBenchContract",
    "Custom Mission": "v2Mission",
  };

  const officers = [
    ["Quartermaster", "Weapons + loadout"],
    ["Scout", "Repository discovery"],
    ["Engineer", "Architecture check"],
    ["Medic", "Risk + repair checks"],
    ["Analyst", "Evidence analysis"],
    ["Judge", "Final verdict"],
    ["Hermes", "Message runner"],
    ["Archivist", "Report storage"],
    ["Challenger", "Battle opposition"],
    ["Commander", "Mission authority"],
  ];

  const weapons = [
    "Static Analysis",
    "Regression Tests",
    "Security Scanner",
    "Battle Compare",
    "Evidence Export",
    "IDE Contract Probe",
  ];

  let state = {
    status: "Standing By",
    workspace: "sergeant",
    branch: "—",
    history: [],
    last: null,
    platform: "IDE",
    currentMission: null,
  };

  function send(payload) {
    try {
      if (typeof window.sergeantHostSend === "function") {
        window.sergeantHostSend(JSON.stringify(payload));
        return true;
      }
    } catch (error) {
      notice(error.message, true);
    }
    return false;
  }

  function notice(message, error = false) {
    const element = $("#hostNotice");
    element.textContent = message || "";
    element.classList.toggle("show", Boolean(message));
    element.classList.toggle("error", error);
  }

  function showPage(id) {
    $$(".page").forEach((page) => page.classList.toggle("active", page.id === id));
    $$('[data-page]').forEach((button) => button.classList.toggle("active", button.dataset.page === id));
  }

  function renderPhase(value) {
    const percent = Math.max(0, Math.min(100, Number(value) || 0));
    $("#progressBar").style.width = `${percent}%`;
    $("#dashboardPhase").style.width = `${percent}%`;
    $("#progressPct").textContent = `${percent}%`;
    const labels = ["Mission Started", "Evidence Collected", "Verification", "Consensus", "Report Generated"];
    $("#timeline").innerHTML = labels.map((label, index) => {
      const threshold = (index + 1) * 20;
      const cssClass = percent >= threshold ? "done" : percent > index * 20 ? "running" : "";
      return `<div class="${cssClass}">${percent >= threshold ? "✓" : index + 1} ${escapeHtml(label)}</div>`;
    }).join("");
  }

  function selectedMission() {
    const type = $('input[name="level"]:checked')?.value || "Repository Review";
    const loadout = $$(".checks label").filter((label) => label.querySelector("input")?.checked).map((label) => label.textContent.trim());
    return {
      type,
      briefing: $("#missionBriefing").value.trim(),
      priority: $("#priority").value,
      provider: $("#providerSelect").value,
      loadout,
    };
  }

  function renderMissionSummary() {
    const mission = selectedMission();
    $("#missionSummary").innerHTML = [
      ["Mission", mission.type],
      ["Workspace", state.workspace],
      ["Priority", mission.priority],
      ["Provider", mission.provider],
      ["Loadout", `${mission.loadout.length} weapon groups`],
      ["Permissions", "Read + Proof"],
      ["Commander", "Ready"],
    ].map(([label, value], index) => `<div class="row"><span>${escapeHtml(label)}</span><b class="${index === 6 ? "pass" : ""}">${escapeHtml(value)}</b></div>`).join("");
  }

  function renderOfficers() {
    const card = (officer, index) => `<div class="officer"><b>${escapeHtml(officer[0])}</b><small>${escapeHtml(officer[1])}</small><div class="row"><span>Status</span><b class="${index < 6 ? "pass" : "work"}">${index < 6 ? "READY" : "IDLE"}</b></div></div>`;
    $("#officers").innerHTML = officers.map(card).join("");
    $("#dashboardOfficers").innerHTML = officers.slice(0, 5).map(card).join("");
    $("#armoury").innerHTML = weapons.map((weapon) => `<div class="weapon"><b>${escapeHtml(weapon)}</b><small>Available weapon · permission gated · evidence output.</small><div class="row"><span>Status</span><b class="pass">READY</b></div></div>`).join("");
  }

  function renderConfidence() {
    const rows = [["Evidence", 98], ["Architecture", 93], ["Security", 96], ["Documentation", 90], ["Commander", 95]];
    $("#confidence").innerHTML = rows.map(([label, percent]) => `<div class="confidence-line"><span>${escapeHtml(label)}</span><span class="bar"><i style="width:${percent}%"></i></span><b>${percent}%</b></div>`).join("");
  }

  function renderDoctrine() {
    const cards = [
      ["Evidence First", "Static findings, runtime proof, UI behavior, docs proof, API results and conflicts are gathered before claims."],
      ["Cross Verification", "Evidence sources are compared and disagreements are investigated rather than averaged away."],
      ["Confidence", "Confidence reflects evidence quality, coverage and unresolved conflicts."],
      ["Human Authority", "Writer mode creates draft patches only. Human approval is required and Sergeant never auto-merges."],
      ["Finish, Then Prove", "Complete the intended implementation, review it, freeze it, then perform clean-clone and runtime proof."],
      ["Claims Match Implementation", "Documentation and marketing claims are checked against actual behavior before release."],
    ];
    $("#doctrineCards").innerHTML = cards.map(([title, description]) => `<div class="evidence"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p></div>`).join("");

    const roadmap = [
      ["Operations", "Live mission monitoring, reusable templates and multi-repository operations."],
      ["Review Collaboration", "Collaborative reviews, replay and shared audit trails."],
      ["Knowledge / Learning", "Knowledge base integration, analytics and recurring-issue trends."],
      ["Plugin / Weapon SDK", "Permission-gated analysis weapons with defined inputs, outputs and evidence formats."],
    ];
    $("#roadmapCards").innerHTML = roadmap.map(([title, description]) => `<div class="evidence"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p><b class="work">POST‑V2</b></div>`).join("");

    const guide = ["What is Sergeant?", "Review Doctrine", "How Sergeant Reviews", "Mission System", "Officers", "Armoury", "Evidence", "Battle Testing", "Post‑V2 Roadmap", "Safety", "FAQ"];
    $("#guideCards").innerHTML = guide.map((title) => `<div class="guide"><b>${escapeHtml(title)}</b><p>Explains how ${escapeHtml(title.toLowerCase())} fits Commander → Mission → Officers → Weapon Manifest → Evidence → Verification → Commander Verdict → Audit Trail.</p></div>`).join("");
  }

  function renderSettings(tab = "general") {
    const settings = {
      general: ["Auto-save reports", "Confirm before launch", "Show commander summary"],
      providers: ["Provider selector", "Cloud / local fallback", "Provider health checks"],
      writer: ["Disabled by default", "Draft patch only", "Human approval required", "Never auto-merge"],
      permissions: ["Owner approval gates", "Read-only default", "Final proof confirmation"],
      ide: ["Workspace awareness", "Active file", "Git branch", "Changed files", "Python / Git / virtual environment"],
      github: ["Repository status", "PR comments planned", "Commit evidence"],
      battle: ["Battle comparison", "UI proof checks", "Regression baseline"],
      debug: ["Runtime logs", "Bridge diagnostics"],
      advanced: ["Export UI contract", "Reset local evidence"],
    };
    $$("#settingTabs button").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
    $("#settingsContent").innerHTML = (settings[tab] || []).map((label) => `<div class="setting"><span>${escapeHtml(label)}</span><span class="toggle"></span></div>`).join("");
  }

  function verdictClass(value) {
    const normalized = String(value || "").toUpperCase();
    return normalized.includes("PASS") || normalized.includes("COMPLETE") || normalized.includes("VERIFIED") ? "pass" : normalized.includes("BLOCK") || normalized.includes("FAIL") ? "danger" : "work";
  }

  function renderEvidence() {
    const findings = Array.isArray(state.last?.findings) ? state.last.findings : [];
    const defaults = [
      ["Static Evidence", "Repository structure, changed files and source findings."],
      ["Runtime Evidence", "Command exit status and captured runtime output."],
      ["UI Evidence", "Command Center controls and rendered behavior."],
      ["Docs Verification", "README, release notes and workflow claims."],
      ["Battle Evidence", "Comparison fixtures, regressions and disagreements."],
      ["External Review", "Imported reviewer evidence when explicitly enabled."],
    ];
    $("#evidenceCards").innerHTML = defaults.map(([title, fallback], index) => {
      const finding = findings[index];
      const description = finding?.message || finding?.evidence || fallback;
      return `<div class="evidence"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p><b class="${state.last ? "pass" : "work"}">${state.last ? "RUNTIME" : "AWAITING MISSION"}</b></div>`;
    }).join("");
  }

  function missionLabel(item) {
    return item?.missionContext?.type || item?.mission || item?.title || "Mission";
  }

  function renderHistory() {
    const history = Array.isArray(state.history) ? state.history : [];
    $("#recentMissions").innerHTML = history.length ? history.slice(0, 3).map((item) => {
      const result = item.result || item.verdict || "—";
      return `<div class="row"><span>${escapeHtml(item.id || "—")} · ${escapeHtml(missionLabel(item))}</span><b class="${verdictClass(result)}">${escapeHtml(result)}</b></div>`;
    }).join("") : '<p class="muted">No runtime missions yet.</p>';

    $("#historyBody").innerHTML = history.map((item) => {
      const result = item.result || item.verdict || "—";
      return `<tr><td>${escapeHtml(item.id || "—")}</td><td>${escapeHtml(item.date || item.finishedAt || "—")}</td><td class="${verdictClass(result)}">${escapeHtml(result)}</td><td>${escapeHtml(missionLabel(item))}</td><td>${escapeHtml(item.duration || "—")}</td></tr>`;
    }).join("");

    $("#latestReport").innerHTML = state.last ? [
      ["Mission", state.last.missionContext?.type || state.last.title],
      ["Verdict", state.last.summary?.verdict || state.last.verdict || "—"],
      ["Provider", state.last.missionContext?.provider || "Default runtime"],
      ["Finished", state.last.finishedAt || "—"],
    ].map(([label, value], index) => `<div class="row"><span>${escapeHtml(label)}</span><b class="${index === 1 ? verdictClass(value) : ""}">${escapeHtml(value)}</b></div>`).join("") : '<p class="muted">No runtime report yet.</p>';
  }

  function renderWorkspaces() {
    const selector = $("#workspaceSelect");
    const workspaces = [...new Set([...(Array.isArray(state.workspaces) ? state.workspaces : []), state.workspace].filter(Boolean))];
    const selected = state.workspace;
    selector.replaceChildren(...workspaces.map((workspace) => new Option(workspace, workspace, workspace === selected, workspace === selected)));
  }

  function applyState(nextState) {
    state = { ...state, ...(nextState || {}) };
    const running = Boolean(state.running) || String(state.status).toLowerCase() === "running";
    const currentMission = state.currentMission || state.last?.missionContext || null;

    $("#sideStatus").textContent = running ? "Reviewing" : state.status;
    $("#sideMessage").textContent = running ? "Mission running against live workspace." : "Mission ready. Awaiting orders.";
    $("#commanderStatus").textContent = running ? "Reviewing" : state.status;
    $("#currentMission").textContent = currentMission?.type || state.runningTitle || state.last?.title || "Repository Review";
    $("#currentWorkspace").textContent = state.workspace;
    $("#workspaceMeta").textContent = `Branch: ${state.branch || "—"} · ${state.changedFilesCount || 0} changed file(s)`;
    $("#commanderVerdict").textContent = state.last?.summary?.verdict || state.last?.verdict || "WAITING";
    $("#commanderVerdict").className = verdictClass(state.last?.summary?.verdict || state.last?.verdict);
    $("#verdictMeta").textContent = state.last ? "Latest runtime evidence loaded." : "No runtime evidence yet.";
    $("#activeFile").textContent = state.activeFile || "—";
    $("#changedFiles").textContent = String(state.changedFilesCount || 0);
    $("#platformName").textContent = state.platform || "IDE";
    $("#runtimePlatform").textContent = `${state.platform || "IDE"} Runtime`;

    renderWorkspaces();
    if (state.settings?.provider) $("#providerSelect").value = state.settings.provider;
    renderPhase(running ? state.progress || 36 : state.last ? 100 : 0);
    $("#operation").textContent = running ? state.runningTitle || "Collecting evidence…" : state.last ? `${state.last.summary?.verdict || state.last.verdict} — report ready.` : "Waiting for runtime…";
    $("#liveLog").textContent = running ? `[${new Date().toLocaleTimeString()}] Mission running through ${state.platform} host…` : state.last ? `[${new Date().toLocaleTimeString()}] Mission completed. Evidence Locker updated.` : "";

    renderHistory();
    renderEvidence();
    renderMissionSummary();
    notice(state.notice || "", Boolean(state.error));
    if (running) showPage("progress");
    else if (state.last?.justFinished) showPage("reports");
  }

  function launch(action) {
    const mission = selectedMission();
    showPage("progress");
    renderPhase(12);
    $("#operation").textContent = "Commander accepted the mission. Waiting for runtime evidence…";
    send({ type: "run", action, mission });
  }

  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    if (action) {
      event.preventDefault();
      launch(action.dataset.action);
      return;
    }
    const targetPage = event.target.closest("[data-page]");
    if (targetPage) {
      event.preventDefault();
      showPage(targetPage.dataset.page);
    }
  });

  $$('input[name="level"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      $$(".mission-types label").forEach((label) => label.classList.toggle("selected", Boolean(label.querySelector("input")?.checked)));
      renderMissionSummary();
    });
  });
  $$(".checks input").forEach((checkbox) => checkbox.addEventListener("change", renderMissionSummary));
  $("#priority").addEventListener("change", renderMissionSummary);
  $("#missionBriefing").addEventListener("input", renderMissionSummary);
  $("#deployBtn").addEventListener("click", () => launch(missionMap[$('input[name="level"]:checked').value]));
  $("#providerSelect").addEventListener("change", () => {
    renderMissionSummary();
    send({ type: "saveSettings", settings: { provider: $("#providerSelect").value } });
  });
  $("#workspaceSelect").addEventListener("change", () => send({ type: "selectWorkspace", workspace: $("#workspaceSelect").value }));
  $("#openLatestReport").addEventListener("click", () => send({ type: "openLast" }));
  $("#exportBattleReport").addEventListener("click", () => send({ type: "exportLast" }));
  $("#copyVerdict").addEventListener("click", () => send({ type: "copyLast" }));
  $("#quickCopy").addEventListener("click", () => send({ type: "copyLast" }));
  $("#refreshMission").addEventListener("click", () => send({ type: "refresh" }));
  $("#refreshReports").addEventListener("click", () => send({ type: "refresh" }));
  $("#settingTabs").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) renderSettings(button.dataset.tab);
  });
  $("#globalSearch").addEventListener("input", () => {
    const query = $("#globalSearch").value.trim().toLowerCase();
    $$(".page.active .panel,.page.active .evidence,.page.active .guide,.page.active .officer,.page.active .weapon").forEach((element) => {
      element.classList.toggle("search-hidden", Boolean(query) && !element.textContent.toLowerCase().includes(query));
    });
  });

  window.addEventListener("message", (event) => {
    if (["sergeantState", "state"].includes(event.data?.type)) applyState(event.data.state);
  });

  setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString(); }, 1000);
  renderOfficers();
  renderConfidence();
  renderDoctrine();
  renderSettings();
  renderEvidence();
  renderHistory();
  renderMissionSummary();
  renderPhase(0);
  if (!send({ type: "ready" })) notice("Standalone preview mode — open through the Sergeant IDE extension for live missions.");
})();
