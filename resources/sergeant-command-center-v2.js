(() => {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const missionMap = {
    'Repository Review': 'reviewWorkspace',
    'Pull Request Review': 'reviewChangedFiles',
    'Release Verification': 'finalProof',
    'Battle Comparison': 'battleTests',
    'Final Proof': 'finalProof',
    'IDE Review': 'ideBenchContract',
    'Custom Mission': 'v2Mission',
  };
  const officers = [
    ['Quartermaster', 'Weapons + loadout'],
    ['Scout', 'Repository discovery'],
    ['Engineer', 'Architecture check'],
    ['Medic', 'Risk + repair checks'],
    ['Analyst', 'Evidence analysis'],
    ['Judge', 'Final verdict'],
    ['Hermes', 'Message runner'],
    ['Archivist', 'Report storage'],
    ['Challenger', 'Battle opposition'],
    ['Commander', 'Mission authority'],
  ];
  const weapons = [
    'Static Analysis',
    'Regression Tests',
    'Security Scanner',
    'Semantic Open-Model Review',
    'Battle Compare',
    'Evidence Export',
    'IDE Contract Probe',
  ];
  let state = {
    status: 'Standing By',
    workspace: 'sergeant',
    branch: '—',
    history: [],
    last: null,
    platform: 'IDE',
    settings: {
      policy: 'preferred',
      provider: 'auto',
      baseUrl: '',
      model: '',
      protocol: 'auto',
      council: 'adaptive',
    },
  };

  const send = (payload) => {
    try {
      if (typeof window.sergeantHostSend === 'function') {
        window.sergeantHostSend(JSON.stringify(payload));
        return true;
      }
    } catch (error) {
      notice(error.message, true);
    }
    return false;
  };

  function notice(message, error = false) {
    const element = $('#hostNotice');
    element.textContent = message || '';
    element.classList.toggle('show', Boolean(message));
    element.classList.toggle('error', error);
  }

  function page(id) {
    $$('.page').forEach((element) => element.classList.toggle('active', element.id === id));
    $$('[data-page]').forEach((button) => button.classList.toggle('active', button.dataset.page === id));
  }

  function phase(progress) {
    const percentage = Math.max(0, Math.min(100, Number(progress) || 0));
    $('#progressBar').style.width = `${percentage}%`;
    $('#dashboardPhase').style.width = `${percentage}%`;
    $('#progressPct').textContent = `${percentage}%`;
    const labels = ['Mission Started', 'Evidence Collected', 'Verification', 'Consensus', 'Report Generated'];
    $('#timeline').innerHTML = labels.map((label, index) => {
      const cutoff = (index + 1) * 20;
      const className = percentage >= cutoff ? 'done' : percentage > index * 20 ? 'running' : '';
      return `<div class="${className}">${percentage >= cutoff ? '✓' : index + 1} ${label}</div>`;
    }).join('');
  }

  function selectedSettings() {
    return {
      policy: $('#llmPolicySelect').value,
      provider: $('#providerSelect').value,
      baseUrl: $('#llmBaseUrlInput').value.trim(),
      model: $('#llmModelInput').value.trim(),
      protocol: $('#llmProtocolSelect').value,
      council: $('#llmCouncilSelect').value,
    };
  }

  function semanticRouteLabel(settings = selectedSettings()) {
    const provider = settings.provider || 'auto';
    const model = settings.model || 'best open model';
    if (settings.policy === 'disabled' || provider === 'disabled') return 'Deterministic only';
    return `${provider} · ${model}`;
  }

  function saveSemanticSettings() {
    const settings = selectedSettings();
    state.settings = { ...state.settings, ...settings };
    $('#semanticRoute').textContent = semanticRouteLabel(settings);
    missionSummary();
    send({ type: 'saveSettings', settings });
  }

  function applySettings(settings = {}) {
    state.settings = { ...state.settings, ...settings };
    const mappings = [
      ['#llmPolicySelect', 'policy'],
      ['#providerSelect', 'provider'],
      ['#llmBaseUrlInput', 'baseUrl'],
      ['#llmModelInput', 'model'],
      ['#llmProtocolSelect', 'protocol'],
      ['#llmCouncilSelect', 'council'],
    ];
    for (const [selector, key] of mappings) {
      const element = $(selector);
      if (element && state.settings[key] !== undefined && state.settings[key] !== null) {
        element.value = String(state.settings[key]);
      }
    }
    $('#semanticRoute').textContent = semanticRouteLabel(state.settings);
  }

  function missionSummary() {
    const mission = $('input[name="level"]:checked')?.value || 'Repository Review';
    const semantic = semanticRouteLabel();
    $('#missionSummary').innerHTML = [
      ['Mission', mission],
      ['Workspace', state.workspace],
      ['Priority', $('#priority').value],
      ['Permissions', 'Read + Proof'],
      ['Semantic Review', semantic],
      ['Commander', 'Ready', 'pass'],
    ].map(([label, value, className = '']) => (
      `<div class="row"><span>${label}</span><b class="${className}">${value}</b></div>`
    )).join('');
  }

  function renderOfficers() {
    const card = (officer, index) => `<div class="officer"><b>${officer[0]}</b><small>${officer[1]}</small><div class="row"><span>Status</span><b class="${index < 6 ? 'pass' : 'work'}">${index < 6 ? 'READY' : 'IDLE'}</b></div></div>`;
    $('#officers').innerHTML = officers.map(card).join('');
    $('#dashboardOfficers').innerHTML = officers.slice(0, 5).map(card).join('');
    $('#armoury').innerHTML = weapons.map((weapon) => `<div class="weapon"><b>${weapon}</b><small>Available weapon · permission gated · evidence output.</small><div class="row"><span>Status</span><b class="pass">READY</b></div></div>`).join('');
  }

  function renderConfidence() {
    const rows = [
      ['Deterministic Evidence', 98],
      ['Architecture', 93],
      ['Security', 96],
      ['Semantic Grounding', 94],
      ['Commander', 95],
    ];
    $('#confidence').innerHTML = rows.map((row) => `<div class="confidence-line"><span>${row[0]}</span><span class="bar"><i style="width:${row[1]}%"></i></span><b>${row[1]}%</b></div>`).join('');
  }

  function renderDoctrine() {
    const cards = [
      ['Evidence First', 'Static findings, runtime proof, semantic findings, UI behavior, docs proof, API results and conflicts are gathered before claims.'],
      ['Grounded Semantic Review', 'Every semantic blocker or major finding must point to supplied repository text, path and line range. Unsupported claims are rejected.'],
      ['Cross Verification', 'Evidence sources are compared and disagreements are investigated rather than averaged away.'],
      ['Confidence', 'Confidence reflects evidence quality, coverage and unresolved conflicts.'],
      ['Human Authority', 'Writer mode creates draft patches only. Human approval is required and Sergeant never auto-merges.'],
      ['Finish, Then Prove', 'Complete the intended implementation, review it, freeze it, then perform clean-clone and runtime proof.'],
      ['Claims Match Implementation', 'Documentation and marketing claims are checked against actual behavior before release.'],
    ];
    $('#doctrineCards').innerHTML = cards.map((card) => `<div class="evidence"><h3>${card[0]}</h3><p>${card[1]}</p></div>`).join('');
    const roadmap = [
      ['Operations', 'Live mission monitoring, reusable templates and multi-repository operations.'],
      ['Review Collaboration', 'Collaborative reviews, replay and shared audit trails.'],
      ['Knowledge / Learning', 'Knowledge base integration, analytics and recurring-issue trends.'],
      ['Plugin / Weapon SDK', 'Permission-gated analysis weapons with defined inputs, outputs and evidence formats.'],
    ];
    $('#roadmapCards').innerHTML = roadmap.map((card) => `<div class="evidence"><h3>${card[0]}</h3><p>${card[1]}</p><b class="work">POST‑V2</b></div>`).join('');
    const guide = ['What is Sergeant?', 'Review Doctrine', 'How Sergeant Reviews', 'Mission System', 'Open-Model Router', 'Officers', 'Armoury', 'Evidence', 'Battle Testing', 'Post‑V2 Roadmap', 'Safety', 'FAQ'];
    $('#guideCards').innerHTML = guide.map((title) => `<div class="guide"><b>${title}</b><p>Explains how ${title.toLowerCase()} fits Commander → Mission → Officers → Weapon Manifest → Deterministic Evidence → Semantic Evidence → Verification → Commander Verdict → Audit Trail.</p></div>`).join('');
  }

  function settings(tab = 'general') {
    const providerDetails = [
      `Policy: ${state.settings.policy || 'preferred'}`,
      `Provider: ${state.settings.provider || 'auto'}`,
      `Model: ${state.settings.model || 'Automatic open-model preference'}`,
      `Protocol: ${state.settings.protocol || 'auto'}`,
      `Council: ${state.settings.council || 'adaptive'}`,
      'API credentials: environment only',
    ];
    const map = {
      general: ['Auto-save reports', 'Confirm before launch', 'Show commander summary'],
      providers: providerDetails,
      writer: ['Disabled by default', 'Draft patch only', 'Human approval required', 'Never auto-merge'],
      permissions: ['Owner approval gates', 'Read-only default', 'Final proof confirmation'],
      ide: ['Workspace awareness', 'Active file', 'Git branch', 'Changed files', 'Python / Git / virtual environment'],
      github: ['Repository status', 'PR comments planned', 'Commit evidence'],
      battle: ['Battle comparison', 'UI proof checks', 'Regression baseline'],
      debug: ['Runtime logs', 'Bridge diagnostics', 'LLM route available through sergeant llm-status'],
      advanced: ['Export UI contract', 'Reset local evidence', 'Required semantic-review policy'],
    };
    $$('#settingTabs button').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
    $('#settingsContent').innerHTML = (map[tab] || []).map((item) => `<div class="setting"><span>${item}</span><span class="toggle"></span></div>`).join('');
  }

  function renderEvidence() {
    const findings = state.last?.findings || [];
    const defaults = [
      ['Static Evidence', 'Repository structure, changed files and source findings.'],
      ['Runtime Evidence', 'Command exit status and captured runtime output.'],
      ['Semantic Evidence', 'Evidence-grounded findings from the selected open model and optional challenger.'],
      ['UI Evidence', 'Command Center controls and rendered behavior.'],
      ['Docs Verification', 'README, release notes and workflow claims.'],
      ['Battle Evidence', 'Comparison fixtures, regressions and disagreements.'],
      ['External Review', 'Imported reviewer evidence when explicitly enabled.'],
    ];
    $('#evidenceCards').innerHTML = defaults.map((item, index) => `<div class="evidence"><h3>${item[0]}</h3><p>${findings[index]?.message || findings[index]?.evidence || item[1]}</p><b class="${state.last ? 'pass' : 'work'}">${state.last ? 'RUNTIME' : 'AWAITING MISSION'}</b></div>`).join('');
  }

  function renderHistory() {
    const history = state.history || [];
    $('#recentMissions').innerHTML = history.slice(0, 3).map((item) => `<div class="row"><span>${item.id || '—'} · ${item.mission || item.title}</span><b class="${String(item.result || item.verdict).includes('PASS') ? 'pass' : 'work'}">${item.result || item.verdict}</b></div>`).join('') || '<p class="muted">No runtime missions yet.</p>';
    $('#historyBody').innerHTML = history.map((item) => `<tr><td>${item.id || '—'}</td><td>${item.date || item.finishedAt || '—'}</td><td class="${String(item.result || item.verdict).includes('PASS') ? 'pass' : 'work'}">${item.result || item.verdict}</td><td>${item.mission || item.title}</td><td>${item.duration || '—'}</td></tr>`).join('');
    $('#latestReport').innerHTML = state.last
      ? `<div class="row"><span>Mission</span><b>${state.last.title}</b></div><div class="row"><span>Verdict</span><b class="${String(state.last.summary?.verdict).includes('PASS') ? 'pass' : 'work'}">${state.last.summary?.verdict}</b></div><div class="row"><span>Finished</span><b>${state.last.finishedAt || '—'}</b></div>`
      : '<p class="muted">No runtime report yet.</p>';
  }

  function apply(snapshot) {
    state = { ...state, ...(snapshot || {}) };
    applySettings(state.settings || {});
    const running = Boolean(state.running) || String(state.status).toLowerCase() === 'running';
    $('#sideStatus').textContent = running ? 'Reviewing' : state.status;
    $('#sideMessage').textContent = running ? 'Mission running against live workspace.' : 'Mission ready. Awaiting orders.';
    $('#commanderStatus').textContent = running ? 'Reviewing' : state.status;
    $('#currentMission').textContent = state.runningTitle || state.last?.title || 'Repository Review';
    $('#currentWorkspace').textContent = state.workspace;
    $('#workspaceMeta').textContent = `Branch: ${state.branch || '—'} · ${state.changedFilesCount || 0} changed file(s)`;
    $('#commanderVerdict').textContent = state.last?.summary?.verdict || state.last?.verdict || 'WAITING';
    $('#verdictMeta').textContent = state.last ? 'Latest runtime evidence loaded.' : 'No runtime evidence yet.';
    $('#activeFile').textContent = state.activeFile || '—';
    $('#changedFiles').textContent = state.changedFilesCount || 0;
    $('#platformName').textContent = state.platform || 'IDE';
    $('#runtimePlatform').textContent = `${state.platform || 'IDE'} Runtime`;
    const workspace = $('#workspaceSelect');
    if (state.workspace && !Array.from(workspace.options).some((option) => option.value === state.workspace)) {
      workspace.add(new Option(state.workspace, state.workspace));
    }
    workspace.value = state.workspace;
    phase(running ? state.progress || 36 : state.last ? 100 : 0);
    $('#operation').textContent = running
      ? state.runningTitle || 'Collecting evidence…'
      : state.last
        ? `${state.last.summary?.verdict || state.last.verdict} — report ready.`
        : 'Waiting for runtime…';
    $('#liveLog').textContent = running
      ? `[${new Date().toLocaleTimeString()}] Mission running through ${state.platform} host using ${semanticRouteLabel(state.settings)}…`
      : state.last
        ? `[${new Date().toLocaleTimeString()}] Mission completed. Evidence Locker updated.`
        : '';
    renderHistory();
    renderEvidence();
    missionSummary();
    settings($('#settingTabs button.active')?.dataset.tab || 'general');
    notice(state.notice || '', Boolean(state.error));
    if (running) page('progress');
    else if (state.last?.justFinished) page('reports');
  }

  function launch(action) {
    page('progress');
    phase(12);
    $('#operation').textContent = 'Commander accepted the mission. Waiting for deterministic and semantic evidence…';
    send({
      type: 'run',
      action,
      briefing: $('#missionBriefing').value,
      priority: $('#priority').value,
      settings: selectedSettings(),
    });
  }

  document.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]');
    if (action) {
      event.preventDefault();
      launch(action.dataset.action);
      return;
    }
    const navigation = event.target.closest('[data-page]');
    if (navigation) {
      event.preventDefault();
      page(navigation.dataset.page);
    }
  });

  $$('input[name="level"]').forEach((radio) => {
    radio.onchange = () => {
      $$('.mission-types label').forEach((label) => label.classList.toggle('selected', label.querySelector('input').checked));
      missionSummary();
    };
  });
  $('#priority').onchange = missionSummary;
  $('#deployBtn').onclick = () => launch(missionMap[$('input[name="level"]:checked').value]);
  for (const selector of ['#llmPolicySelect', '#providerSelect', '#llmBaseUrlInput', '#llmModelInput', '#llmProtocolSelect', '#llmCouncilSelect']) {
    $(selector).addEventListener('change', saveSemanticSettings);
  }
  $('#workspaceSelect').onchange = () => send({ type: 'selectWorkspace', workspace: $('#workspaceSelect').value });
  $('#openLatestReport').onclick = () => send({ type: 'openLast' });
  $('#exportBattleReport').onclick = () => send({ type: 'exportLast' });
  $('#copyVerdict').onclick = $('#quickCopy').onclick = () => send({ type: 'copyLast' });
  $('#refreshMission').onclick = $('#refreshReports').onclick = () => send({ type: 'refresh' });
  $('#settingTabs').onclick = (event) => {
    const button = event.target.closest('button');
    if (button) settings(button.dataset.tab);
  };
  $('#globalSearch').oninput = () => {
    const query = $('#globalSearch').value.trim().toLowerCase();
    $$('.page.active .panel,.page.active .evidence,.page.active .guide,.page.active .officer,.page.active .weapon').forEach((element) => {
      element.classList.toggle('search-hidden', Boolean(query) && !element.textContent.toLowerCase().includes(query));
    });
  };
  window.addEventListener('message', (event) => {
    if (['sergeantState', 'state'].includes(event.data?.type)) apply(event.data.state);
  });
  setInterval(() => { $('#clock').textContent = new Date().toLocaleTimeString(); }, 1000);

  renderOfficers();
  renderConfidence();
  renderDoctrine();
  applySettings(state.settings);
  settings();
  renderEvidence();
  renderHistory();
  missionSummary();
  phase(0);
  if (!send({ type: 'ready' })) {
    notice('Standalone preview mode — open through the Sergeant IDE extension for live missions.');
  }
})();
