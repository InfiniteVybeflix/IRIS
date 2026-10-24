/* ═══════════════════════════════════════════════════════════════════════
   IRIS — Application client
   Single-file app logic: router, chat, agents workspace, apps, settings.
   Every request hits the live backend; every failure is surfaced.
   ═══════════════════════════════════════════════════════════════════════ */
(() => {
  'use strict';

  /* ── Tiny DOM helpers ─────────────────────────────────────────────── */
  const $  = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
  const fmtTime = (iso) => {
    try { return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return String(iso || ''); }
  };
  const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  /* ── Toasts — nothing fails silently ──────────────────────────────── */
  const TOAST_TITLE = { error: 'Something failed', success: 'Success', warn: 'Warning', info: 'IRIS' };
  function toast(msg, type = 'info', title, detail) {
    const stack = $('#toast-stack');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML =
      `<div class="t-title">${esc(title || TOAST_TITLE[type] || 'IRIS')}</div>` +
      (detail ? `<div class="t-detail">${esc(detail)}</div>` : `<div class="t-detail">${esc(msg)}</div>`) +
      `<button class="t-close" aria-label="Dismiss">×</button>`;
    const close = () => el.remove();
    el.querySelector('.t-close').addEventListener('click', close);
    stack.appendChild(el);
    setTimeout(close, type === 'error' ? 14000 : 6000);
    return el;
  }
  const warnConsole = (...a) => { try { console.warn('[IRIS]', ...a); } catch { /* noop */ } };

  /* ── Modal ────────────────────────────────────────────────────────── */
  const Modal = {
    open(title, node) {
      $('#modal-title').textContent = title;
      const body = $('#modal-body');
      body.innerHTML = '';
      body.appendChild(node);
      $('#modal-overlay').hidden = false;
      const f = body.querySelector('input, textarea, select, button');
      if (f) setTimeout(() => f.focus(), 40);
    },
    close() { $('#modal-overlay').hidden = true; $('#modal-body').innerHTML = ''; },
  };
  function confirmDialog(message, confirmLabel = 'Confirm', danger = true) {
    return new Promise((resolve) => {
      const wrap = document.createElement('div');
      wrap.innerHTML =
        `<p style="font-size:13.5px">${esc(message)}</p>` +
        `<div class="form-row">` +
        `<button class="btn btn-secondary" data-act="no">Cancel</button>` +
        `<button class="btn ${danger ? 'btn-danger-ghost' : 'btn-primary'}" data-act="yes">${esc(confirmLabel)}</button></div>`;
      wrap.querySelector('[data-act="no"]').onclick = () => { Modal.close(); resolve(false); };
      wrap.querySelector('[data-act="yes"]').onclick = () => { Modal.close(); resolve(true); };
      Modal.open('Please confirm', wrap);
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { Modal.close(); if (!$('#voice-pop').hidden) Voice.close(); }
  });

  /* ── API client — surfaces every error ────────────────────────────── */
  async function api(path, { method = 'GET', body, silent = false, timeout = 60000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(path, {
        method,
        headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
        credentials: 'same-origin',
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = { __raw: text }; }
      if (!res.ok) {
        const msg = (data && (data.error || data.message)) || `HTTP ${res.status} ${res.statusText}`;
        const err = new Error(msg); err.status = res.status; err.data = data;
        if (!silent) toast(msg, 'error', `Request failed · ${path}`);
        throw err;
      }
      return data;
    } catch (e) {
      if (e.name === 'AbortError') {
        const err = new Error(`Request to ${path} timed out`);
        if (!silent) toast('The server took too long to respond.', 'error', 'Request timed out');
        throw err;
      }
      if (!silent && e.status === undefined) toast(e.message, 'error', 'Network error');
      if (!silent) warnConsole(path, e);
      throw e;
    } finally { clearTimeout(timer); }
  }
  /** For endpoints that answer 200 with {success:false}. */
  function must(data, label = 'Operation') {
    if (data && data.success === false) {
      const msg = data.error || `${label} failed`;
      toast(msg, 'error', label);
      const err = new Error(msg); err.data = data; throw err;
    }
    return data;
  }

  /* ── Theme ────────────────────────────────────────────────────────── */
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem('iris-theme', t); } catch { /* private mode */ }
  }
  applyTheme((() => { try { return localStorage.getItem('iris-theme') || 'dark'; } catch { return 'dark'; } })());
  $('#theme-toggle').addEventListener('click', () =>
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

  /* ── Sidebar (mobile drawer) ──────────────────────────────────────── */
  const sidebar = $('#sidebar'), scrim = $('#scrim');
  const closeSidebar = () => { sidebar.classList.remove('open'); scrim.hidden = true; };
  $('#menu-btn').addEventListener('click', () => { sidebar.classList.add('open'); scrim.hidden = false; });
  scrim.addEventListener('click', closeSidebar);

  /* ── Health probe (sidebar status) ────────────────────────────────── */
  async function pollHealth() {
    try {
      const d = await api('/health', { silent: true, timeout: 20000 });
      $('#sys-dot').dataset.state = 'on';
      $('#sys-label').textContent = `Online · ${d.version || 'IRIS'}`;
    } catch (e) {
      $('#sys-dot').dataset.state = 'off';
      $('#sys-label').textContent = 'Backend offline';
    }
  }
  setInterval(pollHealth, 30000);

  /* ── Voice input (browser SpeechRecognition — real, local mic) ────── */
  const Voice = {
    rec: null, listening: false, finalText: '',
    supported() { return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window; },
    open() {
      if (!this.supported()) {
        toast('This browser has no speech recognition. Chrome or Edge support it.', 'warn', 'Voice unavailable');
        return;
      }
      $('#voice-pop').hidden = false;
      this.setState('idle', 'Ready. Click “Start listening” and speak.');
    },
    close() { this.stop(); $('#voice-pop').hidden = true; },
    setState(state, text) {
      const dots = { idle: 'off', listening: 'busy', error: 'off' };
      $('#voice-dot').dataset.state = dots[state] || 'off';
      $('#voice-state-label').textContent = state === 'listening' ? 'Listening…' : 'Voice';
      if (text) $('#voice-text').textContent = text;
    },
    start() {
      if (this.listening) return this.stop();
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.rec = new SR();
      this.rec.lang = navigator.language || 'en-US';
      this.rec.interimResults = true;
      this.rec.continuous = false;
      this.finalText = '';
      this.rec.onresult = (ev) => {
        let interim = '', final = '';
        for (const r of ev.results) (r.isFinal ? final += r[0].transcript : interim += r[0].transcript);
        this.finalText = final;
        const preview = (final || interim || '…').trim();
        $('#voice-text').textContent = preview;
        if (final) {
          $('#voice-send-chat').disabled = false;
          this.setState('idle', `${final.trim()} — press “Send to chat”.`);
        }
      };
      this.rec.onerror = (ev) => {
        this.setState('error', `Recognition error: ${ev.error}. Check mic permissions.`);
        if (ev.error === 'not-allowed') toast('Microphone permission was denied.', 'warn', 'Mic blocked');
        this.listening = false;
      };
      this.rec.onend = () => { this.listening = false; $('#voice-start').textContent = 'Start listening'; };
      try {
        this.rec.start();
        this.listening = true;
        $('#voice-start').textContent = 'Stop';
        this.setState('listening', 'Listening… speak now.');
      } catch (e) { toast(e.message, 'error', 'Could not start recognition'); }
    },
    stop() { if (this.rec && this.listening) { try { this.rec.stop(); } catch { /* noop */ } } },
    sendToChat() {
      if (!this.finalText.trim()) return;
      navigate('chat');
      const input = $('#chat-input');
      input.value = this.finalText.trim();
      input.focus();
      input.dispatchEvent(new Event('input'));
      this.close();
    },
  };
  $('#voice-btn').addEventListener('click', () => Voice.open());
  $('#voice-close').addEventListener('click', () => Voice.close());
  $('#voice-start').addEventListener('click', () => Voice.start());
  $('#voice-send-chat').addEventListener('click', () => Voice.sendToChat());

  /* ── Chat ─────────────────────────────────────────────────────────── */
  const Chat = {
    sessionId: null, messages: [], sending: false, ctrl: null,
    load() {
      try { this.sessionId = localStorage.getItem('iris-session'); this.messages = JSON.parse(localStorage.getItem('iris-chat') || '[]'); } catch { /* fresh */ }
      this.messages.forEach((m) => this.render(m));
      this.scroll();
    },
    persist() {
      try {
        localStorage.setItem('iris-chat', JSON.stringify(this.messages.slice(-40)));
        if (this.sessionId) localStorage.setItem('iris-session', this.sessionId);
      } catch { /* quota — ignore, messages stay in memory */ }
    },
    scroll() { const s = $('#chat-scroll'); s.scrollTop = s.scrollHeight; },
    render(m) {
      const hero = $('#chat-hero'); if (hero) hero.remove();
      const col = $('#chat-col');
      const el = document.createElement('div');
      el.className = `msg msg-${m.role === 'user' ? 'user' : 'assistant'}`;
      const steps = (m.steps && m.steps.length)
        ? `<div class="msg-steps">${m.steps.slice(0, 6).map((s) =>
            `<div class="msg-step"><span class="step-name">${esc(s.name)}</span><span>${esc(s.text)}</span></div>`).join('')}</div>` : '';
      const bodyHtml = m.error
        ? `<div class="msg-content">${esc(m.text)}</div>
           <div class="msg-error">The request failed. ${esc(m.error)}
             <br><button class="btn btn-secondary btn-sm" data-retry>Retry</button></div>`
        : `<div class="msg-content">${this.md(m.text)}</div>`;
      el.innerHTML =
        `<div class="msg-avatar">${m.role === 'user' ? 'You' :
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a7 7 0 0 1 7 7c0 2.4-1.2 4.2-2.6 5.6-.9.9-1.4 1.9-1.4 3.1V19a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2v-1.3c0-1.2-.5-2.2-1.4-3.1C6.2 13.2 5 11.4 5 9a7 7 0 0 1 7-7Z"/></svg>'}</div>
         <div class="msg-body">
           <div class="msg-role">${m.role === 'user' ? 'You' : 'IRIS'}${m.time ? `<span class="muted" style="font-weight:400">· ${esc(m.time)}</span>` : ''}</div>
           ${steps}${bodyHtml}
         </div>`;
      if (m.error) el.querySelector('[data-retry]').addEventListener('click', () => this.send(m.text));
      else {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';
        const copy = document.createElement('button');
        copy.className = 'icon-btn'; copy.title = 'Copy'; copy.textContent = '⧉';
        copy.addEventListener('click', async () => {
          try { await navigator.clipboard.writeText(m.text); toast('Copied to clipboard.', 'success'); }
          catch { toast('Clipboard is blocked by the browser.', 'warn'); }
        });
        actions.appendChild(copy);
        el.querySelector('.msg-body').appendChild(actions);
      }
      col.appendChild(el);
      this.scroll();
    },
    /** Minimal, safe markdown: escaped first, then fences/inline code/bold. */
    md(text) {
      const parts = String(text || '').split(/```(?:\w+)?\n?/);
      let html = '';
      for (let i = 0; i < parts.length; i++) {
        const seg = esc(parts[i]);
        if (i % 2 === 1) html += `<pre><code>${seg}</code></pre>`;
        else html += seg
          .replace(/`([^`\n]+)`/g, '<code>$1</code>')
          .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
          .split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
      }
      return html;
    },
    async send(textRaw) {
      const text = String(textRaw ?? $('#chat-input').value).trim();
      if (!text || this.sending) return;
      $('#chat-input').value = '';
      $('#chat-input').style.height = 'auto';
      this.messages.push({ role: 'user', text, time: clock() });
      this.render(this.messages[this.messages.length - 1]);
      this.persist();

      this.sending = true;
      this.setSendingUI(true);
      const typing = document.createElement('div');
      typing.className = 'msg msg-assistant';
      typing.innerHTML = `<div class="msg-avatar">IRIS</div><div class="msg-body">
        <div class="msg-role">IRIS</div>
        <div class="typing-dots"><i></i><i></i><i></i></div></div>`;
      $('#chat-col').appendChild(typing); this.scroll();

      this.ctrl = new AbortController();
      try {
        const d = await api('/api/chat', {
          method: 'POST', timeout: 180000,
          body: { message: text, session_id: this.sessionId || undefined },
        });
        must(d, 'Chat');
        typing.remove();
        this.sessionId = d.session_id || this.sessionId;
        const steps = (d.status_updates || []).map((u) => ({
          name: esc(u.stage || u.step || u.status || u.tool || 'step'),
          text: esc(String(u.message || u.detail || u.output || '')).slice(0, 140),
        }));
        this.messages.push({
          role: 'assistant', text: d.response || '(empty response)', steps,
          emotion: d.emotion, time: clock(),
        });
        this.render(this.messages[this.messages.length - 1]);
        this.persist();
        if (d.proactive_suggestion && typeof d.proactive_suggestion === 'string') {
          toast(d.proactive_suggestion.slice(0, 160), 'info', 'Proactive suggestion');
        }
        if (localStorage.getItem('iris-tts') === '1') this.speak(d.response || '');
      } catch (e) {
        typing.remove();
        this.messages.push({ role: 'assistant', text: 'I could not complete that request.', error: e.message, time: clock() });
        this.render(this.messages[this.messages.length - 1]);
        this.persist();
      } finally {
        this.sending = false; this.setSendingUI(false); this.ctrl = null;
      }
    },
    setSendingUI(on) {
      const btn = $('#chat-send');
      btn.disabled = on;
      btn.querySelector('span').textContent = on ? '…' : 'Send';
      btn.style.opacity = on ? '0.6' : '1';
    },
    speak(text) {
      try {
        if (!('speechSynthesis' in window)) return;
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(String(text).slice(0, 600));
        u.lang = navigator.language || 'en-US';
        speechSynthesis.speak(u);
      } catch { /* TTS is best-effort */ }
    },
  };
  function initChat() {
    Chat.load();
    const input = $('#chat-input');
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 180) + 'px'; });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); Chat.send(); }
    });
    $('#chat-send').addEventListener('click', () => Chat.send());
    $('#chat-mic').addEventListener('click', () => Voice.open());
  }

  /* ── Router ───────────────────────────────────────────────────────── */
  const ROUTES = {
    'chat':            { title: 'Chat',       sub: 'Multi-agent AI assistant', init: initChat, load: null },
    'agents':          { title: 'Agents',     sub: 'Delegate tasks — each run gets its own tab', init: initAgents, load: loadAgentsView },
    'apps':            { title: 'Apps',       sub: 'Built-in tools, live APIs', init: null, load: loadAppsHub },
    'apps/calendar':   { title: 'Calendar',   sub: 'Schedule and events', init: initCalendarApp, load: loadCalendar },
    'apps/notes':      { title: 'Notes',      sub: 'Personal knowledge', init: initNotes, load: loadNotes },
    'apps/calculator': { title: 'Calculator', sub: 'Standard · statistics · units', init: initCalculator, load: null },
    'apps/projects':   { title: 'Projects',   sub: 'Generate real scaffolds', init: initProjects, load: loadProjects },
    'apps/vision':     { title: 'Vision',     sub: 'Server-side frames + analysis', init: initVision, load: null },
    'apps/math':       { title: 'Math',       sub: 'Symbolic engine', init: initMath, load: null },
    'apps/phone':      { title: 'Phone',      sub: 'ADB bridge control', init: initPhone, load: loadPhone },
    'settings':        { title: 'Settings',   sub: 'Provider · models & scripts · integrations · system', init: initSettings, load: loadSettingsView },
  };
  const inited = new Set();
  function navigate(route) { location.hash = `#/${route}`; }
  function currentRoute() {
    const h = (location.hash || '').replace(/^#\/?/, '');
    return ROUTES[h] ? h : 'chat';
  }
  function render() {
    const r = currentRoute();
    const def = ROUTES[r];
    $$('.view').forEach((v) => { v.hidden = true; });
    const viewId = 'view-' + (r === 'apps' ? 'apps' : r.split('/').pop());
    const view = document.getElementById(viewId);
    if (view) view.hidden = false;
    $('#view-title').textContent = def.title;
    $('#view-sub').textContent = def.sub;
    $$('.nav-item').forEach((a) => a.classList.toggle('active', a.dataset.route === r));
    closeSidebar();
    if (!inited.has(r)) { if (def.init) def.init(); inited.add(r); }
    if (def.load) Promise.resolve(def.load()).catch(() => { /* load fns toast their own errors */ });
    document.title = `${def.title} — IRIS`;
  }
  window.addEventListener('hashchange', render);

  /* ══════════════════════════ AGENTS ════════════════════════════════ */
  const Agents = {
    list: [], filter: '', specialty: 'All', tabs: [], activeTab: null, seq: 0,
  };
  async function loadAgentsView() {
    await Promise.all([loadAgents(), loadActivity()]);
  }
  async function loadAgents() {
    const listEl = $('#agent-list');
    listEl.innerHTML = '<div class="empty-state skeleton" style="height:120px"></div>';
    try {
      const d = await api('/api/omnis/agents', { timeout: 90000 });
      must(d, 'Agent registry');
      Agents.list = d.agents || [];
      renderAgentFilters();
      renderAgentList();
      const badge = $('#agents-count');
      badge.textContent = `${Agents.list.length} registered`;
      badge.className = 'badge accent';
    } catch (e) {
      listEl.innerHTML = `<div class="empty-state">The registry could not be loaded.<br>${esc(e.message)}<br><br>
        <button class="btn btn-secondary btn-sm" onclick="location.reload()">Retry</button></div>`;
      $('#agents-count').textContent = 'unavailable';
      $('#agents-count').className = 'badge err';
    }
  }
  function renderAgentFilters() {
    const specs = new Set();
    Agents.list.forEach((a) => (a.specialties || []).forEach((s) => specs.add(String(s).toLowerCase())));
    const chips = ['All', ...Array.from(specs).slice(0, 8)];
    $('#agent-filters').innerHTML = chips.map((c) =>
      `<button class="chip ${c === Agents.specialty ? 'active' : ''}" data-spec="${esc(c)}">${esc(c)}</button>`).join('');
    $$('#agent-filters .chip').forEach((c) => c.addEventListener('click', () => {
      Agents.specialty = c.dataset.spec;
      renderAgentFilters(); renderAgentList();
    }));
  }
  function renderAgentList() {
    const q = Agents.filter.toLowerCase();
    const list = Agents.list.filter((a) => {
      const name = String(a.name || '').toLowerCase();
      const cls = String(a.class || '').toLowerCase();
      const skills = (a.specialties || []).join(' ').toLowerCase();
      const okSpec = Agents.specialty === 'All' || skills.includes(Agents.specialty.toLowerCase());
      return okSpec && (!q || name.includes(q) || cls.includes(q) || skills.includes(q));
    });
    const el = $('#agent-list');
    if (!list.length) { el.innerHTML = '<div class="empty-state">No agents match this filter.</div>'; return; }
    el.innerHTML = '';
    for (const a of list) {
      const card = document.createElement('div');
      card.className = 'agent-card';
      const skills = (a.specialties || []).slice(0, 4);
      card.innerHTML =
        `<div class="agent-top">
           <span class="agent-name">${esc(a.name)}</span>
           <span class="agent-class">${esc(a.class || 'interface')}</span>
         </div>
         <div class="agent-skills">${skills.map((s) => `<span class="skill-tag">${esc(s)}</span>`).join('') ||
           '<span class="skill-tag">general</span>'}</div>
         <div class="roster-cta">
           ${a.delegatable
             ? '<button class="btn btn-primary btn-sm" data-delegate>Delegate task</button>'
             : '<span class="badge">not delegatable</span>'}
           <button class="btn btn-secondary btn-sm" data-inspect>Details</button>
         </div>`;
      card.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-delegate]')) { openDelegateModal(a); return; }
        if (ev.target.closest('[data-inspect]')) {
          const info = document.createElement('div');
          info.innerHTML = `<div class="kv-list">${
            Object.entries({ name: a.name, class: a.class, delegatable: a.delegatable, specialties: (a.specialties || []).join(', ') })
              .map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join('')
          }</div>`;
          Modal.open(`Agent · ${a.name}`, info);
          return;
        }
        $$('.agent-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        if (a.delegatable) openDelegateModal(a);
      });
      el.appendChild(card);
    }
  }
  function openDelegateModal(agent, presetTask) {
    const wrap = document.createElement('div');
    wrap.innerHTML =
      `<p class="muted" style="font-size:12.5px">Task for <strong>${esc(agent.name)}</strong> — the agent runs it for real and the result opens in its own workspace tab.</p>
       <textarea class="input" rows="4" data-task placeholder="Describe the task precisely…">${esc(presetTask || '')}</textarea>
       <div class="form-row"><button class="btn btn-primary" data-run>Run task</button></div>`;
    const run = async () => {
      const task = wrap.querySelector('[data-task]').value.trim();
      if (!task) { toast('Describe the task first.', 'warn'); return; }
      Modal.close();
      await runDelegation(agent, task);
    };
    wrap.querySelector('[data-run]').onclick = run;
    wrap.querySelector('[data-task]').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run();
    });
    Modal.open('Delegate to agent', wrap);
  }
  async function runDelegation(agent, task) {
    const id = `t${++Agents.seq}`;
    Agents.tabs.push({ id, agent: agent.name, task, status: 'running', started: Date.now(), out: '' });
    updateAgentsBadge();
    renderTabs();
    switchTab(id);
    try {
      const d = await api('/api/omnis/delegate', {
        method: 'POST', timeout: 300000,
        body: { agent: agent.name, task: { description: task, request: task } },
      });
      const tab = Agents.tabs.find((t) => t.id === id);
      if (!tab) return;
      if (d && d.success === false) {
        tab.status = 'failed';
        tab.out = `The agent reported an error:\n${d.error || 'unknown error'}`;
      } else {
        tab.status = 'done';
        tab.out = formatDelegation(d);
      }
    } catch (e) {
      const tab = Agents.tabs.find((t) => t.id === id);
      if (tab) { tab.status = 'failed'; tab.out = `Request failed:\n${e.message}`; }
    }
    renderTabs();
    updateAgentsBadge();
    loadActivity(); // refresh the real OMNIS execution log
  }
  function formatDelegation(d) {
    if (d == null) return '(no output)';
    const pick = d.result ?? d.output ?? d.response ?? d.message;
    if (typeof pick === 'string' && pick.trim()) return pick;
    const { manifest, skills, ...rest } = d;
    const clean = JSON.stringify(rest, (k, v) => (typeof v === 'string' && v.length > 4000 ? v.slice(0, 4000) + '…[truncated]' : v), 2);
    return clean.length > 2 ? clean : JSON.stringify(d, null, 2);
  }
  const TABS_EMPTY = $('#tabs-empty');
  function renderTabs() {
    const strip = $('#agent-tabs');
    if (!Agents.tabs.length) {
      strip.innerHTML = '';
      strip.appendChild(TABS_EMPTY);
      TABS_EMPTY.hidden = false;
      $('#agent-panels').innerHTML = '';
      return;
    }
    TABS_EMPTY.hidden = true;
    strip.innerHTML = Agents.tabs.map((t) =>
      `<div class="agent-tab ${t.id === Agents.activeTab ? 'active' : ''}" role="tab" data-tab="${t.id}">
         <span class="dot" data-state="${t.status === 'running' ? 'busy' : t.status === 'failed' ? 'off' : 'on'}"></span>
         <span class="t-name">${esc(t.agent)}</span>
         <button class="t-close" data-close="${t.id}" aria-label="Close tab">×</button>
       </div>`).join('');
    $$('[data-tab]', strip).forEach((el) => el.addEventListener('click', (ev) => {
      if (ev.target.closest('[data-close]')) {
        const id = ev.target.closest('[data-close]').dataset.close;
        Agents.tabs = Agents.tabs.filter((t) => t.id !== id);
        if (Agents.activeTab === id) Agents.activeTab = Agents.tabs[0]?.id || null;
        updateAgentsBadge(); renderTabs();
        return;
      }
      switchTab(el.dataset.tab);
    }));
    renderTabPanel();
  }
  function switchTab(id) { Agents.activeTab = id; renderTabs(); }
  function renderTabPanel() {
    const panels = $('#agent-panels');
    const t = Agents.tabs.find((x) => x.id === Agents.activeTab);
    if (!t) { panels.innerHTML = '<div class="tab-panel-empty">Select a tab to view its output.</div>'; return; }
    const badge = t.status === 'running' ? '<span class="badge accent">running</span>'
      : t.status === 'failed' ? '<span class="badge err">failed</span>' : '<span class="badge ok">done</span>';
    panels.innerHTML =
      `<div class="task-head">
         <div class="task-line">
           <span class="task-agent">${esc(t.agent)}</span>${badge}
           <span class="task-time">started ${new Date(t.started).toLocaleTimeString()}</span>
           <span class="task-actions">
             <button class="btn btn-secondary btn-sm" data-rerun>Re-run</button>
           </span>
         </div>
         <div class="task-text">${esc(t.task)}</div>
       </div>
       <div class="console ${t.status === 'failed' ? 'err' : ''}">${t.status === 'running'
         ? 'Working… the agent is executing this task on the server.'
         : esc(t.out)}</div>`;
    panels.querySelector('[data-rerun]').addEventListener('click', () => {
      const a = Agents.list.find((x) => x.name === t.agent) || { name: t.agent, delegatable: true };
      openDelegateModal(a, t.task);
    });
  }
  function updateAgentsBadge() {
    const n = Agents.tabs.filter((t) => t.status === 'running').length;
    const b = $('#agents-badge');
    b.hidden = n === 0;
    b.textContent = n;
  }
  async function loadActivity() {
    try {
      const d = await api('/api/omnis/status', { silent: true, timeout: 90000 });
      const log = d.execution_log || [];
      $('#omnis-meta').textContent =
        `OMNIS ${d.version || ''} · session ${String(d.session_id || '').slice(0, 8)} · ${d.cron_jobs ?? 0} cron jobs · ${log.length} recent executions`;
      const runBadge = $('#omnis-running');
      runBadge.textContent = d.running ? 'online' : 'offline';
      runBadge.className = `badge ${d.running ? 'ok' : 'warn'}`;
      const ol = $('#activity-log');
      ol.innerHTML = log.length ? '' : '<li class="empty-state">No executions recorded yet.</li>';
      for (const item of log.slice(-12).reverse()) {
        const li = document.createElement('li');
        li.className = 'log-item';
        const cap = item.capability || item.action || item.task || 'execution';
        const ok = item.success ?? item.ok;
        li.innerHTML =
          `<div class="log-top"><span class="log-cap">${esc(String(cap))}</span>
             <span class="badge ${ok === false ? 'err' : 'ok'}">${ok === false ? 'error' : 'ok'}</span>
             <span class="log-time">${esc(item.timestamp || item.time || item.at || '')}</span></div>
           ${item.error ? `<div class="log-detail">${esc(String(item.error)).slice(0, 200)}</div>` : ''}`;
        ol.appendChild(li);
      }
    } catch (e) {
      $('#omnis-meta').textContent = `OMNIS status unavailable — ${e.message}`;
    }
  }
  function initAgents() {
    $('#agent-search').addEventListener('input', (e) => { Agents.filter = e.target.value; renderAgentList(); });
    $('#omnis-refresh').addEventListener('click', () => loadAgentsView());
  }

  /* ══════════════════════════ APPS HUB ══════════════════════════════ */
  async function loadAppsHub() {
    setBadge('app-badge-notes', async () => {
      const d = await api('/api/notes', { silent: true });
      const n = Array.isArray(d) ? d.length : (d.notes ? d.notes.length : 0);
      return { ok: true, text: `${n} notes` };
    });
    setBadge('app-badge-calendar', async () => {
      const d = await api('/api/calendar/today', { silent: true });
      const evs = d.events || [];
      return { ok: true, text: `${evs.length} today` };
    });
    setBadge('app-badge-projects', async () => {
      const d = await api('/api/projects', { silent: true });
      return { ok: true, text: `${(d.projects || []).length} projects` };
    });
    setBadge('app-badge-phone', async () => {
      const d = await api('/api/phone/device-info', { silent: true, timeout: 15000 });
      const connected = d && d.success !== false && d.device_info || d.connected;
      return connected ? { ok: true, text: 'connected' } : { ok: false, text: 'offline' };
    });
  }
  async function setBadge(id, fn) {
    const el = document.getElementById(id);
    if (!el) return;
    try {
      const r = await fn();
      el.hidden = false;
      el.textContent = r.text;
      el.className = `app-badge badge ${r.ok ? '' : 'warn'}`;
    } catch (e) {
      el.hidden = false;
      el.textContent = 'unavailable';
      el.className = 'app-badge badge warn';
      warnConsole(id, e.message);
    }
  }

  /* ══════════════════════════ CALENDAR ══════════════════════════════ */
  const Cal = { month: new Date(), selected: null, events: [] };
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  async function loadCalendar() {
    $('#cal-month-label').textContent = Cal.month.toLocaleDateString([], { month: 'long', year: 'numeric' });
    const first = new Date(Cal.month.getFullYear(), Cal.month.getMonth(), 1);
    const last = new Date(Cal.month.getFullYear(), Cal.month.getMonth() + 1, 0);
    try {
      const d = await api(`/api/calendar/events?start=${ymd(first)}&end=${ymd(last)}`, { timeout: 30000 });
      must(d, 'Calendar');
      Cal.events = d.events || [];
    } catch (e) {
      Cal.events = [];
      $('#cal-grid').innerHTML = `<div class="empty-state">Calendar unavailable — ${esc(e.message)}</div>`;
      return;
    }
    renderCalGrid();
    loadUpcoming();
  }
  function eventsOn(day) {
    return Cal.events.filter((ev) => String(ev.start_time || ev.start || '').slice(0, 10) === ymd(day));
  }
  function renderCalGrid() {
    const grid = $('#cal-grid');
    grid.innerHTML = '';
    const y = Cal.month.getFullYear(), m = Cal.month.getMonth();
    const firstDow = (new Date(y, m, 1).getDay() + 6) % 7; // Monday-first
    const start = new Date(y, m, 1 - firstDow);
    const today = new Date();
    for (let i = 0; i < 42; i++) {
      const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      const cell = document.createElement('div');
      cell.className = 'cal-cell' +
        (day.getMonth() !== m ? ' out' : '') +
        (ymd(day) === ymd(today) ? ' today' : '') +
        (Cal.selected && ymd(day) === Cal.selected ? ' selected' : '');
      const evs = eventsOn(day);
      if (evs.length) cell.classList.add('has-events');
      cell.innerHTML = `<span class="cal-num">${day.getDate()}</span>` +
        evs.slice(0, 3).map((ev) => {
          const t = String(ev.start_time || ev.start || '').slice(11, 16);
          return `<span class="cal-ev">${t ? `<span class="ev-time">${esc(t)}</span>` : ''}${esc(ev.title || 'event')}</span>`;
        }).join('') +
        (evs.length > 3 ? `<span class="cal-ev">+${evs.length - 3} more</span>` : '');
      cell.addEventListener('click', () => { Cal.selected = ymd(day); renderCalGrid(); renderCalDay(day); });
      grid.appendChild(cell);
    }
  }
  function eventRow(ev) {
    const row = document.createElement('div');
    row.className = 'event-item';
    const t = String(ev.start_time || ev.start || '');
    row.innerHTML =
      `<div class="ev-body">
         <div class="ev-title">${esc(ev.title || 'Untitled')}</div>
         <div class="ev-sub">${esc(t.slice(11, 16) || 'all day')}${ev.location ? ' · ' + esc(ev.location) : ''}${ev.category ? ' · ' + esc(ev.category) : ''}</div>
       </div>
       <button class="icon-btn" title="Delete event" aria-label="Delete event">×</button>`;
    row.querySelector('button').addEventListener('click', async () => {
      if (!await confirmDialog(`Delete “${ev.title}”?`)) return;
      try {
        must(await api(`/api/calendar/events/${encodeURIComponent(ev.id || ev.event_id)}`, { method: 'DELETE' }), 'Delete event');
        toast('Event deleted.', 'success');
        loadCalendar();
      } catch { /* toasted */ }
    });
    return row;
  }
  function renderCalDay(day) {
    $('#cal-day-title').textContent = day.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
    const list = $('#cal-day-list');
    const evs = eventsOn(day);
    list.innerHTML = '';
    if (!evs.length) { list.innerHTML = '<div class="empty-state">No events this day.</div>'; return; }
    evs.forEach((ev) => list.appendChild(eventRow(ev)));
  }
  async function loadUpcoming() {
    try {
      const d = await api('/api/calendar/upcoming?hours=24', { silent: true });
      const list = $('#cal-upcoming-list');
      const evs = d.events || [];
      list.innerHTML = '';
      if (!evs.length) { list.innerHTML = '<div class="empty-state">Nothing scheduled in the next 24 hours.</div>'; return; }
      evs.forEach((ev) => list.appendChild(eventRow(ev)));
      if (!Cal.selected) {
        $('#cal-day-title').textContent = 'Today';
        const today = new Date();
        renderCalDay(today);
      }
    } catch (e) {
      $('#cal-upcoming-list').innerHTML = `<div class="empty-state">Upcoming unavailable — ${esc(e.message)}</div>`;
    }
  }
  function initCalendarApp() {
    $('#cal-prev').addEventListener('click', () => { Cal.month = new Date(Cal.month.getFullYear(), Cal.month.getMonth() - 1, 1); loadCalendar(); });
    $('#cal-next').addEventListener('click', () => { Cal.month = new Date(Cal.month.getFullYear(), Cal.month.getMonth() + 1, 1); loadCalendar(); });
    $('#cal-today').addEventListener('click', () => { Cal.month = new Date(); Cal.selected = null; loadCalendar(); });
    $('#cal-export').addEventListener('click', () => { window.location.href = '/api/calendar/export'; toast('Exporting calendar as .ics …', 'info'); });
    $('#cal-add').addEventListener('click', () => {
      const wrap = document.createElement('div');
      wrap.innerHTML =
        `<div class="form-grid">
           <label class="field span2"><span>Title *</span><input class="input" data-f="title" placeholder="Team sync"></label>
           <label class="field"><span>Date *</span><input class="input" type="date" data-f="date"></label>
           <label class="field"><span>Start time *</span><input class="input" type="time" data-f="time" value="09:00"></label>
           <label class="field"><span>End time</span><input class="input" type="time" data-f="end"></label>
           <label class="field"><span>Category</span><input class="input" data-f="category" placeholder="general"></label>
           <label class="field span2"><span>Location</span><input class="input" data-f="location" placeholder="Optional"></label>
           <label class="field span2"><span>Description</span><textarea class="input" rows="2" data-f="description"></textarea></label>
         </div>
         <div class="form-row"><button class="btn btn-primary" data-save>Create event</button></div>`;
      wrap.querySelector('[data-f="date"]').value = ymd(Cal.selected ? new Date(Cal.selected) : new Date());
      wrap.querySelector('[data-save]').onclick = async () => {
        const g = (k) => wrap.querySelector(`[data-f="${k}"]`).value.trim();
        if (!g('title') || !g('date') || !g('time')) { toast('Title, date and start time are required.', 'warn'); return; }
        const start = `${g('date')}T${g('time')}:00`;
        try {
          must(await api('/api/calendar/events', { method: 'POST', body: {
            title: g('title'), start_time: start,
            end_time: g('end') ? `${g('date')}T${g('end')}:00` : null,
            location: g('location') || null, category: g('category') || 'general',
            description: g('description') || null,
          } }), 'Create event');
          toast('Event created.', 'success');
          Modal.close();
          loadCalendar();
        } catch { /* toasted */ }
      };
      Modal.open('New event', wrap);
    });
  }

  /* ══════════════════════════ NOTES ═════════════════════════════════ */
  const Notes = { list: [], activeId: null, search: '' };
  async function loadNotes() {
    try {
      const d = await api('/api/notes', { timeout: 30000 });
      Notes.list = Array.isArray(d) ? d : (d.notes || []);
    } catch (e) {
      Notes.list = [];
      $('#notes-list').innerHTML = `<div class="empty-state">Notes unavailable — ${esc(e.message)}</div>`;
      return;
    }
    renderNotesList();
    const badge = $('#badge-notes');
    badge.hidden = Notes.list.length === 0;
    badge.textContent = Notes.list.length;
  }
  function renderNotesList() {
    const el = $('#notes-list');
    const q = Notes.search.toLowerCase();
    const filtered = Notes.list.filter((n) =>
      !q || String(n.title || '').toLowerCase().includes(q) || String(n.content || '').toLowerCase().includes(q));
    filtered.sort((a, b) => (b.pinned - a.pinned) || new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
    el.innerHTML = '';
    if (!filtered.length) { el.innerHTML = `<div class="empty-state">${q ? 'No notes match.' : 'No notes yet — create one.'}</div>`; return; }
    for (const n of filtered) {
      const item = document.createElement('div');
      item.className = `note-item ${n.id === Notes.activeId ? 'active' : ''}`;
      item.innerHTML =
        `<div class="n-title">${n.pinned ? '<span class="n-pin">★</span>' : ''}${esc(n.title || 'Untitled')}</div>
         <div class="n-preview">${esc(String(n.content || '').slice(0, 90))}</div>
         <div class="n-meta">${esc(n.category || 'general')}${n.updated_at ? ' · ' + esc(fmtTime(n.updated_at)) : ''}</div>`;
      item.addEventListener('click', () => selectNote(n.id));
      el.appendChild(item);
    }
  }
  function selectNote(id) {
    const n = Notes.list.find((x) => x.id === id);
    if (!n) return;
    Notes.activeId = id;
    renderNotesList();
    $('#editor-empty').hidden = true;
    $('#editor-body').hidden = false;
    $('#note-title').value = n.title || '';
    $('#note-content').value = n.content || '';
    $('#note-category').value = n.category || '';
    $('#note-tags').value = Array.isArray(n.tags) ? n.tags.join(', ') : (n.tags || '');
    $('#note-meta').textContent = `Updated ${n.updated_at ? fmtTime(n.updated_at) : '—'}${n.pinned ? ' · pinned' : ''}`;
    $('#note-pin').textContent = n.pinned ? 'Unpin' : 'Pin';
  }
  function collectEditor() {
    const tags = $('#note-tags').value.split(',').map((t) => t.trim()).filter(Boolean);
    return {
      title: $('#note-title').value.trim(),
      content: $('#note-content').value,
      category: $('#note-category').value.trim() || 'general',
      tags,
    };
  }
  function initNotes() {
    $('#notes-search').addEventListener('input', (e) => { Notes.search = e.target.value; renderNotesList(); });
    $('#note-new').addEventListener('click', () => {
      Notes.activeId = null;
      renderNotesList();
      $('#editor-empty').hidden = true;
      $('#editor-body').hidden = false;
      $('#note-title').value = ''; $('#note-content').value = '';
      $('#note-category').value = ''; $('#note-tags').value = '';
      $('#note-meta').textContent = 'New note';
      $('#note-pin').textContent = 'Pin';
      $('#note-title').focus();
    });
    $('#note-save').addEventListener('click', async () => {
      const data = collectEditor();
      if (!data.title) { toast('Give the note a title first.', 'warn'); return; }
      try {
        if (Notes.activeId) {
          must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}`, { method: 'PUT', body: data }), 'Save note');
          toast('Note saved.', 'success');
        } else {
          const d = must(await api('/api/notes', { method: 'POST', body: data }), 'Create note');
          Notes.activeId = (d.note && d.note.id) || d.id || null;
          toast('Note created.', 'success');
        }
        loadNotes();
      } catch { /* toasted */ }
    });
    $('#note-pin').addEventListener('click', async () => {
      if (!Notes.activeId) { toast('Save the note first.', 'warn'); return; }
      const n = Notes.list.find((x) => x.id === Notes.activeId);
      try {
        must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}/pin`, { method: 'POST', body: { pinned: !(n && n.pinned) } }), 'Pin note');
        loadNotes().then(() => selectNote(Notes.activeId));
      } catch { /* toasted */ }
    });
    $('#note-delete').addEventListener('click', async () => {
      if (!Notes.activeId) { toast('Nothing to delete yet.', 'warn'); return; }
      if (!await confirmDialog('Delete this note permanently?')) return;
      try {
        must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}`, { method: 'DELETE' }), 'Delete note');
        toast('Note deleted.', 'success');
        Notes.activeId = null;
        $('#editor-body').hidden = true;
        $('#editor-empty').hidden = false;
        loadNotes();
      } catch { /* toasted */ }
    });
  }

  /* ══════════════════════════ CALCULATOR ════════════════════════════ */
  const Calc = {
    expr: '', result: '0', fresh: false,
    history: (() => { try { return JSON.parse(localStorage.getItem('iris-calc') || '[]'); } catch { return []; } })(),
    press(k) {
      if (k === 'C') { this.expr = ''; this.result = '0'; }
      else if (k === '⌫') { this.expr = this.expr.slice(0, -1); }
      else if (k === '=') { return this.equals(); }
      else if (k === '±') {
        const m = this.expr.match(/(\d+\.?\d*)$/);
        if (m) {
          const start = this.expr.length - m[1].length;
          this.expr = this.expr.slice(0, start) + '(' + (this.expr[start] === '-' ? m[1] : '-' + m[1]) + ')';
        } else this.expr = '-' + this.expr;
      } else if (k === '%') {
        if (/\d$/.test(this.expr)) this.expr += '%';
      } else {
        if (this.fresh && /\d/.test(k)) { this.expr = ''; }
        this.fresh = false;
        if ('+−×÷'.includes(k) && this.expr === '' && k !== '−') return;
        if (k === ')' && (this.expr.match(/\(/g) || []).length <= (this.expr.match(/\)/g) || []).length) return;
        if (/[)]\d/.test(this.expr.slice(-2)) && /\d/.test(k)) this.expr += '×';
        this.expr += k;
      }
      this.fresh = false;
      this.paint();
    },
    equals() {
      if (!this.expr.trim()) return;
      let value;
      try {
        value = this.evaluate(this.expr);
        if (!isFinite(value)) throw new Error('not finite');
      } catch (e) {
        this.result = 'Error';
        toast(`Could not evaluate “${this.expr}” — ${e.message}`, 'warn', 'Calculator');
        this.paint();
        return;
      }
      const rounded = Math.round(value * 1e10) / 1e10;
      this.history.unshift({ e: this.expr, r: String(rounded) });
      this.history = this.history.slice(0, 30);
      try { localStorage.setItem('iris-calc', JSON.stringify(this.history)); } catch { /* noop */ }
      this.result = String(rounded);
      this.expr = String(rounded);
      this.fresh = true;
      this.paint(); this.paintHistory();
    },
    /** Recursive-descent evaluator — no eval(), supports + − × ÷ ( ) % */
    evaluate(src) {
      const s = src.replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-').replace(/\s+/g, '');
      let i = 0;
      const peek = () => s[i];
      function parseExpr() {
        let v = parseTerm();
        while (peek() === '+' || peek() === '-') { const op = s[i++]; const r = parseTerm(); v = op === '+' ? v + r : v - r; }
        return v;
      }
      function parseTerm() {
        let v = parseFactor();
        while (peek() === '*' || peek() === '/') { const op = s[i++]; const r = parseFactor(); if (op === '/') { if (r === 0) throw new Error('division by zero'); v /= r; } else v *= r; }
        return v;
      }
      function parseFactor() {
        let v = parseUnary();
        while (peek() === '%') { i++; v /= 100; }
        return v;
      }
      function parseUnary() {
        if (peek() === '-') { i++; return -parseUnary(); }
        if (peek() === '+') { i++; return parseUnary(); }
        if (peek() === '(') {
          i++;
          const v = parseExpr();
          if (peek() !== ')') throw new Error('missing )');
          i++;
          return v;
        }
        const m = /^\d+\.?\d*(?:[eE][+-]?\d+)?/.exec(s.slice(i));
        if (!m) throw new Error(`unexpected “${s[i] || 'end'}”`);
        i += m[0].length;
        return parseFloat(m[0]);
      }
      const v = parseExpr();
      if (i < s.length) throw new Error(`unexpected “${s[i]}”`);
      return v;
    },
    paint() {
      $('#calc-expr').innerHTML = esc(this.expr) || '&nbsp;';
      $('#calc-result').textContent = this.result;
    },
    paintHistory() {
      const ul = $('#calc-history');
      ul.innerHTML = this.history.length ? '' : '<li class="empty-state">No calculations yet.</li>';
      this.history.forEach((h) => {
        const li = document.createElement('li');
        li.innerHTML = `<div class="h-e">${esc(h.e)} =</div><div class="h-r">${esc(h.r)}</div>`;
        li.addEventListener('click', () => { this.expr = h.r; this.result = h.r; this.fresh = true; this.paint(); });
        ul.appendChild(li);
      });
    },
  };
  function initCalculator() {
    $$('#calc-keypad .calc-key').forEach((b) => b.addEventListener('click', () => Calc.press(b.dataset.k)));
    Calc.paint(); Calc.paintHistory();
    $('#calc-clear-history').addEventListener('click', () => {
      Calc.history = [];
      try { localStorage.removeItem('iris-calc'); } catch { /* noop */ }
      Calc.paintHistory();
      toast('History cleared.', 'info');
    });
    $$('.chip[data-calc-tab]').forEach((chip) => chip.addEventListener('click', () => {
      $$('.chip[data-calc-tab]').forEach((c) => c.classList.toggle('active', c === chip));
      ['standard', 'stats', 'units'].forEach((t) => { $('#calc-' + t).hidden = chip.dataset.calcTab !== t; });
    }));
    $('#stats-compute').addEventListener('click', async () => {
      const raw = $('#stats-input').value.trim();
      const values = raw.split(/[\n,;]+/).map((x) => parseFloat(x)).filter((x) => !Number.isNaN(x));
      if (!values.length) { toast('Enter at least one valid number.', 'warn'); return; }
      try {
        const d = must(await api('/api/math/statistics', { method: 'POST', body: { values, operation: 'all' } }), 'Statistics');
        const stats = d.statistics || d.result || d;
        const rows = [['count', 'Count'], ['mean', 'Mean'], ['median', 'Median'], ['mode', 'Mode'], ['stdev', 'Std dev'], ['variance', 'Variance'], ['min', 'Min'], ['max', 'Max'], ['sum', 'Sum']];
        const grid = $('#stats-output');
        grid.hidden = false;
        grid.innerHTML = rows.filter(([k]) => stats[k] !== undefined)
          .map(([k, label]) => `<div class="stat-card"><div class="s-k">${label}</div><div class="s-v">${esc(String(stats[k]))}</div></div>`)
          .join('') || `<div class="result-console">${esc(JSON.stringify(stats, null, 2))}</div>`;
        toast('Statistics computed.', 'success');
      } catch { /* toasted */ }
    });
    $('#unit-convert').addEventListener('click', async () => {
      const value = parseFloat($('#unit-value').value);
      const from = $('#unit-from').value.trim(), to = $('#unit-to').value.trim();
      if (Number.isNaN(value) || !from || !to) { toast('Value, from and to are required.', 'warn'); return; }
      try {
        const d = must(await api('/api/math/convert', { method: 'POST', body: { value, from, to } }), 'Convert');
        const out = $('#unit-output');
        out.hidden = false;
        out.classList.add('ok');
        out.textContent = d.result !== undefined ? `${value} ${from} = ${d.result} ${to}` : JSON.stringify(d, null, 2);
      } catch { /* toasted */ }
    });
    document.addEventListener('keydown', (e) => {
      if (currentRoute() !== 'apps/calculator' || !$('#calc-standard') || !$('#calc-standard').offsetParent) return;
      if (e.target.matches('input, textarea, select')) return;
      const map = { '*': '×', '/': '÷', '-': '−', '+': '+', '(': '(', ')': ')', '%': '%', '.': '.', Enter: '=', Backspace: '⌫', Escape: 'C' };
      if (/^\d$/.test(e.key)) { Calc.press(e.key); e.preventDefault(); }
      else if (map[e.key]) { Calc.press(map[e.key]); e.preventDefault(); }
    });
  }

  /* ══════════════════════════ PROJECTS ══════════════════════════════ */
  async function loadProjects() {
    try {
      const t = await api('/api/projects/templates', { silent: true });
      const templates = t.templates || [];
      const sel = $('#project-template');
      sel.innerHTML = templates.map((tp) => {
        const id = typeof tp === 'string' ? tp : (tp.id || tp.name);
        const label = typeof tp === 'string' ? tp : (tp.name || tp.id);
        return `<option value="${esc(id)}">${esc(label)}</option>`;
      }).join('');
      $('#projects-templates-badge').textContent = `${templates.length} templates`;
      $('#projects-templates-badge').className = 'badge accent';
    } catch (e) {
      $('#project-template').innerHTML = `<option value="">unavailable</option>`;
      $('#projects-templates-badge').textContent = 'templates unavailable';
      $('#projects-templates-badge').className = 'badge err';
    }
    try {
      const d = await api('/api/projects', { silent: true });
      const list = $('#projects-list');
      const projects = d.projects || [];
      list.innerHTML = projects.length ? '' : '<div class="empty-state">No projects generated yet.</div>';
      projects.forEach((p) => {
        const el = document.createElement('div');
        el.className = 'project-item';
        el.innerHTML = `<div class="p-name">${esc(p.name || p.title || 'project')}</div>
          <div class="p-sub">${esc([p.template, p.status, p.path, p.created_at && fmtTime(p.created_at)].filter(Boolean).join(' · '))}</div>`;
        list.appendChild(el);
      });
    } catch (e) {
      $('#projects-list').innerHTML = `<div class="empty-state">Projects list unavailable — ${esc(e.message)}</div>`;
    }
  }
  function initProjects() {
    $('#projects-refresh').addEventListener('click', loadProjects);
    $('#project-generate').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const name = $('#project-name').value.trim();
      const template = $('#project-template').value;
      const description = $('#project-desc').value.trim();
      if (!name) { toast('Project name is required.', 'warn'); return; }
      if (!template) { toast('Template list is unavailable — refresh first.', 'warn'); return; }
      btn.classList.add('loading');
      const out = $('#project-output');
      out.hidden = true;
      try {
        const d = must(await api('/api/projects/generate', { method: 'POST', timeout: 300000, body: { name, template, description } }), 'Generate project');
        out.hidden = false;
        out.className = 'result-console ok';
        out.textContent = typeof d.result === 'string' ? d.result : JSON.stringify(d, null, 2);
        toast(`Project “${name}” generated.`, 'success');
        loadProjects();
      } catch (err) {
        out.hidden = false;
        out.className = 'result-console err';
        out.textContent = `Generation failed: ${err.message}`;
      } finally { btn.classList.remove('loading'); }
    });
  }

  /* ══════════════════════════ VISION ════════════════════════════════ */
  const Vision = { polling: null, errors: 0 };
  function initVision() {
    $('#vision-start').addEventListener('click', async () => {
      const source = $('#vision-source').value;
      try {
        must(await api('/api/vision/stream/start', { method: 'POST', body: { source, interval: 2.0 } }), 'Start stream');
        $('#vision-state').textContent = `streaming · ${source}`;
        $('#vision-state').className = 'badge accent';
        $('#vision-start').disabled = true;
        $('#vision-stop').disabled = false;
        Vision.errors = 0;
        startVisionPolling();
        toast(`Vision stream started (${source}).`, 'success');
      } catch { /* toasted */ }
    });
    $('#vision-stop').addEventListener('click', async () => {
      stopVisionPolling();
      try { await api('/api/vision/stream/stop', { method: 'POST', silent: true }); } catch { /* best effort */ }
      $('#vision-state').textContent = 'idle';
      $('#vision-state').className = 'badge';
      $('#vision-start').disabled = false;
      $('#vision-stop').disabled = true;
      toast('Vision stream stopped.', 'info');
    });
    $('#vision-analyze').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const question = $('#vision-question').value.trim() || 'What do you see?';
      btn.classList.add('loading');
      try {
        const d = await api('/api/vision/analyze', { method: 'POST', timeout: 120000, body: { question } });
        const out = $('#vision-output');
        out.hidden = false;
        if (d.success === false) { out.className = 'result-console err'; out.textContent = `Analysis failed: ${d.error || 'unknown error'}`; }
        else {
          out.className = 'result-console ok';
          out.textContent = d.analysis || d.description || d.result || JSON.stringify(d, null, 2);
        }
      } catch (err) {
        const out = $('#vision-output');
        out.hidden = false; out.className = 'result-console err';
        out.textContent = `Analysis request failed: ${err.message}`;
      } finally { btn.classList.remove('loading'); }
    });
  }
  function startVisionPolling() {
    stopVisionPolling();
    Vision.polling = setInterval(async () => {
      try {
        const d = await api('/api/vision/frame', { silent: true, timeout: 10000 });
        if (d && d.frame) {
          Vision.errors = 0;
          const feed = $('#vision-feed');
          let img = feed.querySelector('img');
          if (!img) { feed.innerHTML = ''; img = document.createElement('img'); feed.appendChild(img); }
          img.src = `data:image/jpeg;base64,${d.frame}`;
        }
      } catch (e) {
        if (++Vision.errors >= 3) { stopVisionPolling(); toast('Vision polling failed 3 times — stream stopped.', 'error'); }
      }
    }, 1500);
  }
  function stopVisionPolling() { if (Vision.polling) { clearInterval(Vision.polling); Vision.polling = null; } }

  /* ══════════════════════════ MATH ══════════════════════════════════ */
  function initMath() {
    $$('#math-ops [data-op]').forEach((btn) => btn.addEventListener('click', async () => {
      const op = btn.dataset.op;
      const expression = $('#math-expression').value.trim();
      if (!expression) { toast('Enter an expression first.', 'warn'); return; }
      btn.classList.add('loading');
      const body = { expression };
      if (op === 'solve' || op === 'differentiate') body.variable = $('#math-var').value.trim() || 'x';
      if (op === 'differentiate') body.order = parseInt($('#math-order').value, 10) || 1;
      if (op === 'integrate') {
        body.variable = $('#math-var').value.trim() || 'x';
        const lim = $('#math-limits').value.trim();
        if (lim) {
          const parts = lim.split(',').map((x) => parseFloat(x));
          if (parts.length === 2 && parts.every((n) => !Number.isNaN(n))) body.limits = parts;
        }
      }
      try {
        const d = await api(`/api/math/${op}`, { method: 'POST', timeout: 60000, body });
        const out = $('#math-output');
        out.hidden = false;
        if (d.success === false) { out.className = 'result-console err'; out.textContent = `Error: ${d.error || 'unknown'}`; }
        else {
          out.className = 'result-console ok';
          out.textContent = d.result !== undefined ? String(d.result)
            : d.solution !== undefined ? String(d.solution)
            : JSON.stringify(d, (k, v) => (typeof v === 'string' && v.length > 2000 ? v.slice(0, 2000) + '…' : v), 2);
        }
      } catch { /* toasted by api() */ }
      finally { btn.classList.remove('loading'); }
    }));
  }

  /* ══════════════════════════ PHONE ═════════════════════════════════ */
  async function loadPhone() {
    const badge = $('#phone-state');
    try {
      const d = await api('/api/phone/device-info', { silent: true, timeout: 20000 });
      const info = d.device_info || d.info || d;
      const connected = d.success !== false && !d.error && Object.keys(info || {}).length;
      badge.textContent = connected ? 'connected' : 'offline';
      badge.className = `badge ${connected ? 'ok' : 'err'}`;
      const kv = $('#phone-device-info');
      const entries = connected
        ? Object.entries(info).filter(([, v]) => ['string', 'number', 'boolean'].includes(typeof v)).slice(0, 10)
        : [];
      kv.innerHTML = entries.length
        ? entries.map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></div>`).join('')
        : '<div class="empty-state">No device connected. Start the ADB bridge (PhoneBridge module) on the host, then refresh.</div>';
    } catch (e) {
      badge.textContent = 'offline';
      badge.className = 'badge err';
      $('#phone-device-info').innerHTML = `<div class="empty-state">Bridge unreachable — ${esc(e.message)}</div>`;
    }
    loadPhoneMessages();
  }
  async function loadPhoneMessages() {
    try {
      const d = await api('/api/phone/messages', { silent: true, timeout: 20000 });
      const msgs = d.messages || [];
      const el = $('#phone-messages');
      el.innerHTML = msgs.length ? '' : '<div class="empty-state">No messages (or bridge offline).</div>';
      msgs.slice(0, 20).forEach((m) => {
        const row = document.createElement('div');
        row.className = 'contact-item';
        row.innerHTML = `<span class="c-name">${esc(m.sender || m.address || m.from || 'unknown')}</span>
          <span class="c-sub">${esc(String(m.body || m.text || m.message || '')).slice(0, 80)}</span>`;
        el.appendChild(row);
      });
    } catch (e) {
      $('#phone-messages').innerHTML = `<div class="empty-state">Messages unavailable — ${esc(e.message)}</div>`;
    }
  }
  function initPhone() {
    $$('[data-phone-cmd]').forEach((btn) => btn.addEventListener('click', async () => {
      btn.classList.add('loading');
      try {
        const d = await api(`/api/phone/${btn.dataset.phoneCmd}`, { method: 'POST', timeout: 30000, body: {} });
        if (d && d.success === false) toast(d.error || 'Action failed', 'error', btn.textContent);
        else toast(d.message || `${btn.textContent} — done.`, 'success', btn.textContent);
      } catch { /* toasted */ }
      finally { btn.classList.remove('loading'); }
    }));
    $('#phone-contacts-btn').addEventListener('click', async () => {
      const q = $('#phone-contact-search').value.trim();
      try {
        const d = await api(`/api/phone/contacts/search${q ? `?q=${encodeURIComponent(q)}` : ''}`, { timeout: 20000 });
        const contacts = d.contacts || [];
        const el = $('#phone-contacts');
        el.innerHTML = contacts.length ? '' : '<div class="empty-state">No contacts found.</div>';
        contacts.slice(0, 30).forEach((c) => {
          const row = document.createElement('div');
          row.className = 'contact-item';
          row.innerHTML = `<span class="c-name">${esc(c.name || c.display_name || 'unknown')}</span><span class="c-sub">${esc(c.number || c.phone || '')}</span>`;
          el.appendChild(row);
        });
      } catch { /* toasted */ }
    });
    $('#phone-msgs-refresh').addEventListener('click', loadPhoneMessages);
  }

  /* ══════════════════════════ SETTINGS ══════════════════════════════ */
  const Settings = { providers: {}, integrations: {}, current: {}, selected: 'auto', catalog: null, jobPoll: {} };
  function initSettings() {
    $$('.settings-tab').forEach((tab) => tab.addEventListener('click', () => {
      $$('.settings-tab').forEach((t) => t.classList.toggle('active', t === tab));
      $$('.settings-pane').forEach((p) => { p.hidden = p.id !== `settings-${tab.dataset.settingsTab}`; });
    }));
    $('#tts-toggle').checked = localStorage.getItem('iris-tts') === '1';
    $('#tts-toggle').addEventListener('change', (e) => {
      localStorage.setItem('iris-tts', e.target.checked ? '1' : '0');
      toast(e.target.checked ? 'Replies will be spoken.' : 'Speech disabled.', 'info');
    });
  }
  async function loadSettingsView() {
    initProviderPane();
    loadModelsPane();
    loadIntegrationsPane();
    loadSystemPane();
  }
  /* ── Provider pane (ported from the old settings page) ── */
  async function initProviderPane() {
    try {
      const [pd, sd] = await Promise.all([
        api('/api/iris/settings/providers'),
        api('/api/iris/settings', { silent: true }),
      ]);
      Settings.providers = pd.providers || {};
      Settings.integrations = pd.integrations || {};
      Settings.current = sd || {};
      Settings.selected = Settings.current.llm_backend || 'auto';
      $('#auto-select').checked = Settings.current.auto_select !== false;
      renderProviderGrid();
      if (Settings.selected !== 'auto') renderProviderFields(Settings.selected);
    } catch (e) {
      $('#provider-grid').innerHTML = `<div class="empty-state">Provider settings unavailable — ${esc(e.message)}</div>`;
    }
  }
  function renderProviderGrid() {
    const cur = Settings.current.providers || {};
    const options = [['auto', { label: 'Auto-select', description: 'IRIS picks the best available provider automatically' }]]
      .concat(Object.entries(Settings.providers));
    $('#provider-grid').innerHTML = options.map(([name, info]) => {
      const active = Settings.selected === name;
      const configured = name !== 'auto' && cur[name] && cur[name].configured;
      return `<div class="provider-option ${active ? 'active' : ''}" data-p="${esc(name)}">
        <input type="radio" name="provider" ${active ? 'checked' : ''}>
        <div>
          <div class="provider-label">
            <span class="p-dot ${configured ? 'configured' : ''}"></span>${esc(info.label)}
            ${info.recommended ? '<span class="badge ok">recommended</span>' : ''}
          </div>
          <div class="provider-desc">${esc(info.description)}</div>
        </div></div>`;
    }).join('');
    $$('#provider-grid .provider-option').forEach((el) => el.addEventListener('click', () => {
      Settings.selected = el.dataset.p;
      renderProviderGrid();
      $('#provider-result').hidden = true;
      if (Settings.selected !== 'auto') renderProviderFields(Settings.selected);
      else $('#provider-fields').innerHTML = '';
    }));
  }
  function renderProviderFields(name) {
    const info = Settings.providers[name];
    if (!info) return;
    const cur = (Settings.current.providers || {})[name] || {};
    $('#provider-fields').innerHTML = info.fields.map((f) => {
      const masked = cur[f.name + '_masked'] || cur[f.name] || '';
      const isMasked = typeof masked === 'string' && masked.includes('••');
      return `<label class="field" style="margin-top:10px"><span>${esc(f.label)}${f.required ? ' *' : ''}</span>
        <input class="input" type="${f.type}" id="field_${esc(name)}_${esc(f.name)}" placeholder="${esc(f.placeholder || '')}" value="${isMasked ? '' : esc(masked)}" autocomplete="off">
        ${isMasked ? `<span class="muted" style="font-size:11.5px">Currently: ${esc(masked)} — leave blank to keep</span>` : ''}</label>`;
    }).join('');
  }
  function gatherConfig(provider) {
    const info = Settings.providers[provider];
    const cfg = {};
    info.fields.forEach((f) => {
      const el = document.getElementById(`field_${provider}_${f.name}`);
      if (el && el.value) cfg[f.name] = el.value;
    });
    return cfg;
  }
  async function testProvider(showModels) {
    if (Settings.selected === 'auto') { toast('Pick a specific provider first (not Auto).', 'warn'); return; }
    const out = $('#provider-result');
    out.hidden = false; out.className = 'result-console'; out.textContent = 'Testing connection…';
    try {
      const d = await api('/api/iris/settings/test', {
        method: 'POST', timeout: 40000,
        body: { provider: Settings.selected, config: gatherConfig(Settings.selected), test_prompt: 'Say hello in 5 words' },
      });
      if (d.success) {
        out.className = 'result-console ok';
        out.textContent = `Connected. ${d.model_count} models available.` + (d.test_response ? `\nTest reply: “${d.test_response}”` : '');
        if (showModels) {
          const list = (d.models || []).map((m) => `  ${m.id}`).join('\n');
          out.textContent += `\n\nModels:\n${list || '  (none)'}`;
          const first = $('#provider-result');
          first.onclick = () => {};
        }
      } else {
        out.className = 'result-console err';
        out.textContent = `Failed: ${d.error || 'unknown error'}`;
        toast(d.error || 'Connection test failed', 'error', 'Provider test');
      }
    } catch (e) {
      out.hidden = false; out.className = 'result-console err';
      out.textContent = `Test request failed: ${e.message}`;
    }
  }
  function initProviderBindings() {
    $('#provider-test').addEventListener('click', () => testProvider(false));
    $('#provider-models').addEventListener('click', () => testProvider(true));
    $('#provider-save').addEventListener('click', saveSettings);
  }
  async function saveSettings(integrationsOnly = false) {
    const payload = integrationsOnly
      ? { integrations: collectIntegrations() }
      : {
          llm_backend: Settings.selected,
          auto_select: $('#auto-select').checked,
          providers: Settings.selected !== 'auto' ? { [Settings.selected]: gatherConfig(Settings.selected) } : {},
          integrations: collectIntegrations(),
        };
    try {
      const d = must(await api('/api/iris/settings', { method: 'POST', body: payload }), 'Save settings');
      if (d.success !== false) { toast('Settings saved.', 'success'); initProviderPane(); }
    } catch { /* toasted */ }
  }
  function collectIntegrations() {
    const out = {};
    for (const [name, info] of Object.entries(Settings.integrations || {})) {
      const cfg = {};
      info.fields.forEach((f) => {
        const el = document.getElementById(`intg_${name}_${f.name}`);
        if (el && el.value) cfg[f.name] = el.value;
      });
      if (Object.keys(cfg).length) out[name] = cfg;
    }
    return out;
  }
  /* ── Models & scripts pane ── */
  async function loadModelsPane() {
    const grid = $('#models-grid');
    grid.innerHTML = '<div class="empty-state skeleton" style="height:140px"></div>';
    try {
      const d = await api('/api/scripts', { timeout: 30000 });
      must(d, 'Model registry');
      Settings.catalog = d;
      const env = d.environment || {};
      $('#models-env').innerHTML =
        `<strong>${env.serverless ? 'Serverless environment (Vercel)' : 'Persistent host'}</strong> — ${esc(env.note || '')}
         <br>Storage: <code>${esc(env.models_dir || 'models/')}</code>${env.installed_gb !== undefined ? ` · installed: ${env.installed_gb} GB` : ''}${env.free_disk_gb !== undefined ? ` · free disk: ${env.free_disk_gb} GB` : ''}`;
      const types = [...new Set(d.models.map((m) => m.type))];
      $('#model-filters').innerHTML = ['all'].concat(types).map((t, i) =>
        `<button class="chip ${i === 0 ? 'active' : ''}" data-type="${esc(t)}">${esc(t)}</button>`).join('');
      $$('#model-filters .chip').forEach((chip) => chip.addEventListener('click', () => {
        $$('#model-filters .chip').forEach((c) => c.classList.toggle('active', c === chip));
        renderModelGrid(chip.dataset.type);
      }));
      renderModelGrid('all');
      renderJobsList(d.jobs || []);
    } catch (e) {
      grid.innerHTML = `<div class="empty-state">Model registry unavailable — ${esc(e.message)}</div>`;
    }
  }
  function renderModelGrid(type) {
    const grid = $('#models-grid');
    const models = (Settings.catalog.models || []).filter((m) => type === 'all' || m.type === type);
    grid.innerHTML = '';
    if (!models.length) { grid.innerHTML = '<div class="empty-state">No models for this type.</div>'; return; }
    models.forEach((m) => {
      const card = document.createElement('div');
      card.className = 'model-card';
      card.innerHTML =
        `<div class="model-top"><span class="model-name">${esc(m.name)}</span><span class="badge">${esc(m.type)}</span></div>
         <div class="model-desc">${esc(m.description)}</div>
         <div class="variant-table">${m.variants.map((v) =>
           `<div class="variant-row"><span>${esc(v.name)}</span><span class="vr-size">${v.size_gb} GB · ≥${v.min_vram_gb} GB VRAM</span></div>`).join('')}</div>
         ${m.pip_dependencies.length ? `<div class="deps-note">pip: ${esc(m.pip_dependencies.join(', '))}</div>` : ''}
         <div class="model-foot">
           <button class="btn btn-primary btn-sm" data-install="${esc(m.id)}">Install</button>
         </div>`;
      card.querySelector('[data-install]').addEventListener('click', () => runScriptJob('install_models', { model: m.id }, `install ${m.id}`));
      grid.appendChild(card);
    });
  }
  async function runScriptJob(script, body, label) {
    try {
      const d = must(await api('/api/scripts/run', { method: 'POST', body: { script, ...body } }), 'Start script');
      toast(`Started “${label}” — job ${d.job_id}.`, 'info');
      openJobConsole(d.job_id, `${label} · ${d.job_id}`);
      pollJob(d.job_id);
    } catch { /* toasted */ }
  }
  function openJobConsole(jobId, title) {
    $('#job-console').hidden = false;
    $('#job-console-title').textContent = title || jobId;
    $('#job-console-out').textContent = 'Waiting for output…';
    $('#job-console').dataset.job = jobId;
  }
  async function pollJob(jobId) {
    if (Settings.jobPoll[jobId]) return;
    Settings.jobPoll[jobId] = setInterval(async () => {
      try {
        const d = await api(`/api/scripts/jobs/${jobId}`, { silent: true, timeout: 15000 });
        const job = d.job;
        if (!job) throw new Error('job vanished');
        if ($('#job-console').dataset.job === jobId) {
          $('#job-console-out').textContent =
            `$ ${job.command}\n\n${job.stdout || '(no stdout yet)'}${job.stderr ? `\n\n[stderr]\n${job.stderr}` : ''}` +
            (job.status === 'running' ? `\n\n… running (${Math.round((Date.now() / 1000 - job.started_at))}s)` : `\n\n→ ${job.status} (exit ${job.exit_code})`);
        }
        if (job.status !== 'running') {
          clearInterval(Settings.jobPoll[jobId]); delete Settings.jobPoll[jobId];
          toast(`Job ${jobId} ${job.status}.`, job.status === 'done' ? 'success' : 'error', 'Script job');
          refreshJobsList();
        } else {
          refreshJobsList();
        }
      } catch (e) {
        clearInterval(Settings.jobPoll[jobId]); delete Settings.jobPoll[jobId];
        toast(`Lost track of job ${jobId}: ${e.message}`, 'warn', 'Script job');
      }
    }, 1500);
  }
  async function refreshJobsList() {
    try {
      const d = await api('/api/scripts/jobs', { silent: true, timeout: 15000 });
      renderJobsList(d.jobs || []);
    } catch { /* silent refresh */ }
  }
  function renderJobsList(jobs) {
    const el = $('#jobs-list');
    $('#jobs-count').textContent = jobs.length;
    el.innerHTML = jobs.length ? '' : '<div class="empty-state">No jobs yet — install a model above.</div>';
    jobs.forEach((j) => {
      const row = document.createElement('div');
      row.className = 'job-item';
      const badge = j.status === 'running' ? '<span class="badge accent">running</span>'
        : j.status === 'done' ? '<span class="badge ok">done</span>'
        : j.status === 'timeout' ? '<span class="badge warn">timeout</span>' : '<span class="badge err">failed</span>';
      row.innerHTML = `${badge}<span class="j-cmd">${esc(j.command)}</span><span class="j-time">${j.duration_s != null ? j.duration_s + 's' : new Date(j.started_at * 1000).toLocaleTimeString()}</span>`;
      row.addEventListener('click', () => {
        openJobConsole(j.job_id, `${j.script} · ${j.job_id}`);
        $('#job-console-out').textContent = `$ ${j.command}\n\n${j.stdout || ''}${j.stderr ? `\n\n[stderr]\n${j.stderr}` : ''}`;
      });
      el.appendChild(row);
    });
  }
  function initModelsBindings() {
    $('#models-refresh').addEventListener('click', loadModelsPane);
    $('#job-console-close').addEventListener('click', () => { $('#job-console').hidden = true; });
  }
  /* ── Integrations pane ── */
  function loadIntegrationsPane() {
    // providers/integrations data is fetched by the provider pane; if it has
    // already arrived, render; otherwise wait briefly and retry once.
    const tryRender = (attempt = 0) => {
      if (Object.keys(Settings.integrations).length) return renderIntegrations();
      if (attempt < 6) return setTimeout(() => tryRender(attempt + 1), 500);
      $('#integrations-grid').innerHTML = '<div class="empty-state">Integrations unavailable — open the Provider tab first or reload.</div>';
    };
    tryRender();
  }
  function renderIntegrations() {
    const cur = Settings.current.integrations || {};
    $('#integrations-grid').innerHTML = Object.entries(Settings.integrations).map(([name, info]) => {
      const c = cur[name] || {};
      const fields = info.fields.map((f) => {
        const masked = c[f.name + '_masked'] || c[f.name] || '';
        const isMasked = typeof masked === 'string' && masked.includes('••');
        return `<label class="field"><span>${esc(f.label)}</span>
          <input class="input" type="${f.type}" id="intg_${esc(name)}_${esc(f.name)}" placeholder="${esc(f.placeholder || '')}" value="${isMasked ? '' : esc(masked)}" autocomplete="off">
          ${isMasked ? `<span class="muted" style="font-size:11px">Currently: ${esc(masked)}</span>` : ''}</label>`;
      }).join('');
      return `<div class="integration-card">
        <div class="i-head"><span class="p-dot ${c.configured ? 'configured' : ''}"></span>${esc(info.label)}</div>
        <div class="i-desc">${esc(info.description)}</div>${fields}</div>`;
    }).join('');
  }
  function initIntegrationsBindings() {
    $('#integrations-save').addEventListener('click', () => saveSettings(true));
  }
  /* ── System pane ── */
  async function loadSystemPane() {
    try {
      const [sys, llm] = await Promise.all([
        api('/api/status', { silent: true }),
        api('/api/llm/status', { silent: true }),
      ]);
      const iris = sys.iris || {};
      $('#system-kv').innerHTML = [
        ['Version', `${iris.version || '—'} ${iris.codename ? '“' + iris.codename + '”' : ''}`],
        ['Status', iris.status || '—'],
        ['Uptime', iris.uptime != null ? JSON.stringify(iris.uptime) : '—'],
        ['Database', llm ? undefined : undefined],
        ['Awareness', iris.awareness != null ? String(iris.awareness) : '—'],
      ].filter(([, v]) => v !== undefined).map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></div>`).join('');
      $('#llm-kv').innerHTML = [
        ['Default backend', llm.default_backend || '—'],
        ['Default model', llm.default_model || '—'],
        ['Fast model', llm.fast_model || '—'],
        ['Deep model', llm.deep_model || '—'],
        ['Backends', (llm.backends || []).map((b) => (typeof b === 'string' ? b : b.name)).join(', ') || '—'],
      ].map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></div>`).join('');
      if (llm.default_backend) {
        const chip = $('#backend-chip');
        chip.hidden = false;
        chip.textContent = `${llm.default_backend}${llm.default_model ? ' · ' + llm.default_model : ''}`;
      }
    } catch (e) {
      $('#system-kv').innerHTML = `<div class="empty-state">System status unavailable — ${esc(e.message)}</div>`;
    }
    try {
      const d = await api('/api/autonomous/status', { silent: true });
      const badge = $('#autonomous-badge');
      const running = d.running || d.enabled || d.status === 'running';
      badge.textContent = running ? 'running' : 'idle';
      badge.className = `badge ${running ? 'ok' : ''}`;
      $('#autonomous-kv').innerHTML = Object.entries(d)
        .filter(([, v]) => ['string', 'number', 'boolean'].includes(typeof v))
        .slice(0, 8)
        .map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></div>`).join('')
        || '<div class="empty-state">No status fields returned.</div>';
    } catch (e) {
      $('#autonomous-kv').innerHTML = `<div class="empty-state">Autonomous engine unavailable — ${esc(e.message)}</div>`;
    }
  }
  function initSystemBindings() {
    $('#system-refresh').addEventListener('click', loadSystemPane);
    $('#autonomous-queue').addEventListener('click', async () => {
      const description = $('#autonomous-task').value.trim();
      if (!description) { toast('Describe the task first.', 'warn'); return; }
      try {
        const d = must(await api('/api/autonomous/queue', { method: 'POST', body: { description } }), 'Queue task');
        toast(`Queued as task ${d.task_id ?? ''}.`, 'success');
        $('#autonomous-task').value = '';
        loadSystemPane();
      } catch { /* toasted */ }
    });
    const consoleFor = (btn, url, label) => btn.addEventListener('click', async () => {
      btn.classList.add('loading');
      try {
        const d = await api(url, { timeout: 120000 });
        const out = $('#system-output');
        out.hidden = false;
        out.className = 'result-console ok';
        out.textContent = JSON.stringify(d, null, 2).slice(0, 8000);
        toast(`${label} done.`, 'success');
      } catch (e) {
        const out = $('#system-output');
        out.hidden = false; out.className = 'result-console err';
        out.textContent = `${label} failed: ${e.message}`;
      } finally { btn.classList.remove('loading'); }
    });
    consoleFor($('#self-analyze'), '/api/self/analyze', 'Codebase analysis');
    consoleFor($('#consciousness-reflect'), '/api/consciousness/reflect', 'Reflection');
  }

  /* ── Boot ─────────────────────────────────────────────────────────── */
  initProviderBindings();
  initModelsBindings();
  initIntegrationsBindings();
  initSystemBindings();
  render();
  pollHealth();
})();

