(() => {
  const TOKEN_KEY = 'sergeantStandaloneToken';
  const SETTINGS_KEY = 'sergeantStandaloneSettings';
  let token = sessionStorage.getItem(TOKEN_KEY) || '';
  let prompting = false;

  const parse = (value, fallback = {}) => {
    try { return JSON.parse(value); } catch (_) { return fallback; }
  };

  const postState = (snapshot = {}, justFinished = false) => {
    const state = { ...(snapshot || {}) };
    if (state.last) state.last = { ...state.last, justFinished };
    window.postMessage({ type: 'sergeantState', state }, window.location.origin);
  };

  const postNotice = (message, error = false) => {
    window.postMessage({
      type: 'sergeantState',
      state: { notice: String(message || ''), error },
    }, window.location.origin);
  };

  async function request(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(path, { ...options, headers, cache: 'no-store' });
    if (response.status === 401 && retry && !prompting) {
      prompting = true;
      const supplied = window.prompt('Enter the Sergeant self-hosted service token. It is kept only in this browser tab.');
      prompting = false;
      if (supplied) {
        token = supplied.trim();
        sessionStorage.setItem(TOKEN_KEY, token);
        return request(path, options, false);
      }
    }
    const payload = await response.json().catch(() => ({ ok: false, error: 'invalid_json_response' }));
    if (!response.ok) {
      const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async function refresh() {
    const state = await request('/api/v1/state');
    const cached = parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    if (cached && Object.keys(cached).length) state.settings = { ...(state.settings || {}), ...cached };
    postState(state, false);
    return state;
  }

  async function latestReport() {
    return request('/api/v1/reports/latest');
  }

  function downloadJson(name, payload) {
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function runMission(message) {
    const body = {
      action: message.action,
      briefing: message.briefing || '',
      priority: message.priority || 'Normal',
      settings: message.settings || {},
    };
    if (message.action === 'reviewCurrentFile') {
      const current = window.prompt('Repository-relative file to review, for example main_review/standalone.py');
      if (!current) throw new Error('Current-file review cancelled because no file was supplied.');
      body.current_file = current.trim();
    }
    if (message.action === 'reviewChangedFiles') {
      const changed = window.prompt('Comma-separated repository-relative changed files');
      if (!changed) throw new Error('Changed-files review cancelled because no files were supplied.');
      body.changed_files = changed.split(',').map((item) => item.trim()).filter(Boolean);
    }
    const result = await request('/api/v1/missions', { method: 'POST', body: JSON.stringify(body) });
    postState(result.state || {}, true);
  }

  async function saveSettings(message) {
    const settings = message.settings || {};
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    const result = await request('/api/v1/settings', {
      method: 'POST',
      body: JSON.stringify({ settings }),
    });
    postState(result.state || { settings }, false);
  }

  async function openLatest() {
    const report = await latestReport();
    const blob = new Blob([`<pre>${String(JSON.stringify(report, null, 2)).replaceAll('&', '&amp;').replaceAll('<', '&lt;')}</pre>`], { type: 'text/html' });
    window.open(URL.createObjectURL(blob), '_blank', 'noopener,noreferrer');
  }

  async function exportLatest() {
    const report = await latestReport();
    downloadJson(`sergeant-${report.mission_id || 'latest-report'}.json`, report);
  }

  async function copyLatest() {
    const report = await latestReport();
    const text = report.payload?.markdown || JSON.stringify(report, null, 2);
    await navigator.clipboard.writeText(text);
    postNotice('Latest Sergeant verdict/report copied to the clipboard.');
  }

  async function handle(raw) {
    const message = typeof raw === 'string' ? parse(raw, {}) : raw || {};
    try {
      switch (message.type) {
        case 'ready':
        case 'refresh':
          await refresh();
          break;
        case 'run':
          await runMission(message);
          break;
        case 'saveSettings':
          await saveSettings(message);
          break;
        case 'openLast':
          await openLatest();
          break;
        case 'exportLast':
          await exportLatest();
          break;
        case 'copyLast':
          await copyLatest();
          break;
        case 'selectWorkspace':
          postNotice('This service instance is locked to its configured repository workspace. Start another instance for another repository.');
          await refresh();
          break;
        default:
          throw new Error(`Unsupported standalone host message: ${message.type || 'missing type'}`);
      }
    } catch (error) {
      postNotice(error.message || String(error), true);
    }
  }

  window.sergeantHostSend = (raw) => {
    void handle(raw);
    return true;
  };
})();
