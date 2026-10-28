/* ═══════════════════════════════════════════════════════════════════════════
   IRIS v1 — Application Shell
   Streaming chat · rising terminals · sessions · agents · apps · settings
   ═══════════════════════════════════════════════════════════════════════════ */
(() => {
  'use strict';

  /* ── Helpers ─────────────────────────────────────────────────────────── */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
  const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const fmtTime = (iso) => {
    try { return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return ''; }
  };
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0; const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    }));

  function toast(msg, type = 'info', label = '') {
    const stack = $('#toast-stack');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span class="t-label">${esc(label || { success: 'OK', error: 'Error', warn: 'Warning' }[type] || 'IRIS')}</span>
      <span class="t-msg">${esc(msg)}</span>`;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add('out');
      setTimeout(() => el.remove(), 300);
    }, type === 'error' ? 12000 : 6000);
  }

  const Modal = {
    overlay: null,
    _el(id) { const el = $(id); if (!el) console.warn('[IRIS] missing element:', id); return el; },
    open(title, node) {
      const t = this._el('#modal-title'), b = this._el('#modal-body'), ov = this._el('#modal-overlay');
      if (!t || !b || !ov) return;
      t.textContent = title;
      b.innerHTML = '';
      b.appendChild(node);
      ov.style.removeProperty('display');   // clear any inline fallback from close()
      ov.hidden = false;
      document.documentElement.classList.add('modal-open');   // lock page scroll
    },
    close() {
      const ov = this._el('#modal-overlay'), b = this._el('#modal-body');
      // Belt-and-suspenders: hidden attr + inline display:none — survives any
      // CSS load failure or specificity conflict, so the page can NEVER stick.
      if (ov) { ov.hidden = true; ov.style.display = 'none'; }
      if (b) b.innerHTML = '';
      document.documentElement.classList.remove('modal-open');
    },
  };
  Modal.overlay = $('#modal-overlay');
  $('#modal-close')?.addEventListener('click', () => Modal.close());
  if (Modal.overlay) Modal.overlay.addEventListener('click', (e) => { if (e.target === Modal.overlay) Modal.close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && Modal.overlay && !Modal.overlay.hidden) Modal.close();
  });

  /* ── API helper ──────────────────────────────────────────────────────── */
  async function api(path, opts = {}) {
    const { timeout = 60000, silent = false, ...fetchOpts } = opts;
    // CRITICAL: callers pass plain JS objects as `body`. fetch() would coerce
    // them to the literal string "[object Object]", and the backend's
    // request.get_json() then rejects it with 400 Bad Request. Stringify
    // objects here so ALL POST bodies are valid JSON.
    if (fetchOpts.body && typeof fetchOpts.body === 'object') {
      fetchOpts.body = JSON.stringify(fetchOpts.body);
    }
    // Attach the session token (Google Sign-In) to every call.
    const token = Auth.token();
    if (token) {
      fetchOpts.headers = { ...(fetchOpts.headers || {}), Authorization: `Bearer ${token}` };
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(path, { ...fetchOpts, signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json', ...(fetchOpts.headers || {}) } });
      let d = null;
      const text = await res.text();
      try { d = JSON.parse(text); } catch { d = { success: false, error: text.slice(0, 300) || res.statusText }; }
      if (!res.ok && d && !d.error) d.error = `HTTP ${res.status}`;
      // Session expired mid-use → back to the sign-in screen (never on the
      // auth endpoints themselves, or we would loop).
      if (res.status === 401 && Auth.token() && !path.startsWith('/api/auth')) {
        Auth.sessionExpired();
      }
      if (!res.ok && !silent) {
        const label = (d && d.error) ? String(d.error) : `HTTP ${res.status}`;
        toast(label, 'error', 'Request failed');
      }
      return d;
    } catch (e) {
      const msg = e.name === 'AbortError' ? `Request timed out after ${Math.round(timeout / 1000)}s` : e.message;
      if (!silent) toast(msg, 'error', 'Network');
      return { success: false, error: msg };
    } finally { clearTimeout(timer); }
  }
  function must(d, what) {
    if (!d || d.success === false || d.error) {
      throw new Error((d && (d.error || d.message)) || `${what} failed`);
    }
    return d;
  }

  /* SSE streaming over POST fetch */
  async function streamSSE(path, body, onEvent, signal) {
    const headers = { 'Content-Type': 'application/json' };
    const token = Auth.token();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(path, {
      method: 'POST', signal,
      headers,
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      let err = `HTTP ${res.status}`;
      try { const j = await res.json(); if (j.error) err = j.error; } catch { /* keep */ }
      throw new Error(err);
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (data === '[DONE]') return;
          try { onEvent(JSON.parse(data)); } catch { /* malformed event */ }
        }
      }
    }
  }

  /* ── Theme: light → dark → system ────────────────────────────────────── */
  const Theme = {
    pref: 'dark',
    media: window.matchMedia('(prefers-color-scheme: light)'),
    apply(pref, save = true) {
      this.pref = pref;
      const resolved = pref === 'system'
        ? (this.media.matches ? 'light' : 'dark')
        : pref;
      document.documentElement.dataset.themePref = pref;
      document.documentElement.dataset.theme = resolved;
      $('meta[name="theme-color"]').setAttribute('content',
        resolved === 'dark' ? '#08090c' : '#f5f6f8');
      if (save) { try { localStorage.setItem('iris-theme-pref', pref); } catch { /* ignore */ } }
    },
    cycle() {
      const order = ['light', 'dark', 'system'];
      const next = order[(order.indexOf(this.pref) + 1) % order.length];
      this.apply(next);
      toast(`Theme: ${next}`, 'info', 'IRIS');
    },
    init() {
      let pref = 'dark';
      try { pref = localStorage.getItem('iris-theme-pref') || 'dark'; } catch { /* ignore */ }
      this.apply(pref, false);
      this.media.addEventListener('change', () => {
        if (this.pref === 'system') this.apply('system', false);
      });
      $('#theme-toggle').addEventListener('click', () => this.cycle());
    },
  };
  Theme.init();

  /* ── Auth (Google Sign-In — session token stays in this browser) ─────── */
  const Auth = {
    KEY: 'iris-session',
    user: null,
    token() { try { return localStorage.getItem(this.KEY) || ''; } catch { return ''; } },
    save(t) { try { localStorage.setItem(this.KEY, t); } catch { /* quota */ } },
    clear() { try { localStorage.removeItem(this.KEY); } catch { /* ignore */ } this.user = null; },
    async restore() {
      const t = this.token();
      if (!t) return false;
      try {
        const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${t}` } });
        const d = await res.json().catch(() => null);
        if (res.ok && d && d.signed_in) { this.user = d.user; return true; }
      } catch { /* offline — fall through to signed-out */ }
      this.clear();
      return false;
    },
    sessionExpired() {
      if (!this.token()) return;
      this.clear();
      showSignIn(true);
      toast('Your session expired — please sign in again.', 'warn');
    },
    signOut() {
      this.clear();
      showSignIn();
      toast('Signed out.', 'success');
    },
  };

  /* ── Health / user chip ────────────────────────────────────────────── */
  let healthTimer = null;
  async function pollHealth() {
    const dot = $('#sys-dot');
    const label = $('#sys-label');
    try {
      const d = await api('/health', { silent: true, timeout: 12000 });
      if (d && d.status) {
        dot.dataset.state = 'on';
        label.textContent = `All systems operational · v${(d.version || '1').replace(/^v/, '')}`;
      } else throw new Error('unhealthy');
    } catch {
      dot.dataset.state = 'off';
      label.textContent = 'Backend unreachable';
    }
  }
  function scheduleHealth() {
    pollHealth();
    healthTimer = setInterval(pollHealth, 30000);
  }
  function renderUserChip() {
    const chip = $('#user-chip');
    if (!chip) return;
    const u = Auth.user;
    if (!u) { chip.hidden = true; return; }
    chip.hidden = false;
    const initials = (u.name || u.email || '?').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
    chip.innerHTML = `
      ${u.picture ? `<img class="u-avatar" src="${esc(u.picture)}" alt="" referrerpolicy="no-referrer">` : `<span class="u-avatar u-initials">${esc(initials)}</span>`}
      <span class="u-info"><span class="u-name">${esc(u.name || 'Signed in')}</span>
      <span class="u-email">${esc(u.email || '')}</span></span>
      <button class="icon-btn" id="signout-btn" title="Sign out" aria-label="Sign out">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>
      </button>`;
    $('#signout-btn').addEventListener('click', () => Auth.signOut());
  }

  /* ══════════════════════════════════════════════════════════════════════
     RISING TERMINALS — every agent / tool action becomes a live terminal
     ══════════════════════════════════════════════════════════════════════ */
  const Terminals = {
    stack: [],
    maxVisible: 4,
    spawn(id, title, kind = 'tool', command = '') {
      let t = this.stack.find((x) => x.id === id);
      if (t) return t;
      const host = $('#terminals');
      const el = document.createElement('div');
      el.className = 'terminal';
      el.dataset.status = 'running';
      el.innerHTML = `
        <div class="terminal-head">
          <span class="t-lights" aria-hidden="true"><i></i><i></i><i></i></span>
          <span class="t-head-dot"></span>
          <span class="t-title">${esc(title)}</span>
          <span class="t-status">running…</span>
        </div>
        <div class="terminal-body"></div>
        <div class="terminal-foot"></div>`;
      host.appendChild(el);
      const body = $('.terminal-body', el);
      if (command) this.line(id, command, 'cmd');
      t = {
        id, el, body, lineCount: 0, status: 'running',
        head: $('.terminal-head', el),
        foot: $('.terminal-foot', el),
        statusEl: $('.t-status', el),
        closeTimer: null,
      };
      this.stack.push(t);
      // trim old terminals if too many
      const visible = this.stack.filter((x) => !x.el.classList.contains('closing'));
      if (visible.length > this.maxVisible) this.close(visible[0].id, 600);
      // click header = collapse/expand
      t.head.addEventListener('click', () => el.classList.toggle('collapsed'));
      return t;
    },
    line(id, text, cls = '') {
      const t = this.stack.find((x) => x.id === id);
      if (!t) return;
      const div = document.createElement('span');
      div.className = `tline ${cls}`;
      div.textContent = text;
      t.body.appendChild(div);
      t.lineCount += 1;
      // keep the terminal bounded
      if (t.lineCount > 400) {
        t.body.removeChild(t.body.firstChild);
        t.lineCount -= 1;
      }
      t.body.scrollTop = t.body.scrollHeight;
    },
    setStatus(id, status, summary = '') {
      const t = this.stack.find((x) => x.id === id);
      if (!t) return;
      t.status = status;
      t.el.dataset.status = status;
      t.statusEl.textContent = status === 'ok' ? 'done'
        : status === 'error' ? 'failed' : 'running…';
      if (summary) t.foot.textContent = summary;
      // auto-collapse finished terminals shortly after they end
      if (status === 'ok' || status === 'error') {
        setTimeout(() => t.el.classList.add('collapsed'), 1400);
        this.close(id, 20000);
      }
    },
    close(id, delayMs = 0) {
      const t = this.stack.find((x) => x.id === id);
      if (!t || t.el.classList.contains('closing')) return;
      setTimeout(() => {
        t.el.classList.add('closing');
        setTimeout(() => {
          t.el.remove();
          this.stack = this.stack.filter((x) => x.id !== id);
        }, 320);
      }, delayMs);
    },
    closeAll() { this.stack.slice().forEach((t) => this.close(t.id, 0)); },
  };

  /* ══════════════════════════════════════════════════════════════════════
     CHAT — sessions, streaming, edit / retry / delete
     ══════════════════════════════════════════════════════════════════════ */
  const Chat = {
    sessions: [],
    activeId: null,
    messages: [],       // [{id, role, content, thinking, tools[], error?}]
    sending: false,
    ctrl: null,
    liveEl: null,       // streaming assistant bubble
    liveText: '',
    liveThinking: '',
    liveTools: [],
    renderTimer: null,

    /* ── sessions ─────────────────────────────────────────────────────── */
    async loadSessions(keepActive = true) {
      const d = await api('/api/chat/sessions', { silent: true, timeout: 20000 });
      if (!d || d.success === false) {
        $('#chat-list').innerHTML = `<div class="chat-list-empty">Sessions unavailable — ${esc((d && d.error) || 'check server')}</div>`;
        return;
      }
      this.sessions = d.sessions || [];
      if (!keepActive || !this.activeId) {
        this.activeId = this.sessions.length ? this.sessions[0].session_id : null;
      }
      this.renderSessions();
    },
    renderSessions() {
      const list = $('#chat-list');
      const empty = $('#chat-list-empty');
      list.innerHTML = '';
      if (!this.sessions.length) {
        list.appendChild(empty);
        empty.hidden = false;
        return;
      }
      for (const s of this.sessions) {
        const el = document.createElement('div');
        el.className = `chat-item ${s.session_id === this.activeId ? 'active' : ''}`;
        el.innerHTML = `
          <span class="ci-title">${esc(s.title || 'Untitled chat')}</span>
          <span class="ci-actions">
            <button data-rename title="Rename">✎</button>
            <button data-del title="Delete">🗑</button>
          </span>`;
        el.addEventListener('click', (ev) => {
          if (ev.target.closest('[data-rename]')) { this.renameSession(s); return; }
          if (ev.target.closest('[data-del]')) { this.deleteSession(s); return; }
          if (this.sending) { toast('Wait for the current reply to finish (or stop it).', 'warn'); return; }
          this.switchSession(s.session_id);
          closeSidebar();
        });
        list.appendChild(el);
      }
    },
    async newSession() {
      if (this.sending) { toast('Stop the current reply first.', 'warn'); return; }
      const sid = uuid();
      const d = await api('/api/chat/sessions', { method: 'POST', silent: true, body: { session_id: sid, title: 'New chat' } });
      if (!d || d.success === false) { toast((d && d.error) || 'Could not create chat', 'error'); return; }
      this.activeId = sid;
      this.messages = [];
      this.renderMessages();
      this.renderHero(true);
      await this.loadSessions(true);
      navigate('chat');
      $('#chat-input').focus();
    },
    async renameSession(s) {
      const wrap = document.createElement('div');
      wrap.innerHTML = `
        <label class="field"><span>Chat title</span>
          <input class="input" data-title value="${esc(s.title || '')}" maxlength="80"></label>
        <div class="form-row end">
          <button class="btn btn-secondary btn-sm" data-cancel>Cancel</button>
          <button class="btn btn-primary btn-sm" data-save>Save</button>
        </div>`;
      Modal.open('Rename chat', wrap);
      const input = $('[data-title]', wrap);
      input.focus(); input.select();
      $('[data-cancel]', wrap).addEventListener('click', () => Modal.close());
      $('[data-save]', wrap).addEventListener('click', async () => {
        const title = input.value.trim();
        if (!title) return;
        const d = await api(`/api/chat/sessions/${encodeURIComponent(s.session_id)}`, { method: 'PATCH', body: { title } });
        if (d && d.success) { Modal.close(); toast('Chat renamed.', 'success'); this.loadSessions(true); }
      });
    },
    async deleteSession(s) {
      const wrap = document.createElement('div');
      wrap.innerHTML = `
        <p>Delete <strong>${esc(s.title || 'this chat')}</strong> and all its messages? This cannot be undone.</p>
        <div class="form-row end">
          <button class="btn btn-secondary btn-sm" data-cancel>Cancel</button>
          <button class="btn btn-danger btn-sm" data-del>Delete</button>
        </div>`;
      Modal.open('Delete chat', wrap);
      $('[data-cancel]', wrap).addEventListener('click', () => Modal.close());
      $('[data-del]', wrap).addEventListener('click', async () => {
        const d = await api(`/api/chat/sessions/${encodeURIComponent(s.session_id)}`, { method: 'DELETE' });
        if (d && d.success) {
          Modal.close();
          toast('Chat deleted.', 'success');
          if (s.session_id === this.activeId) { this.activeId = null; this.messages = []; this.renderMessages(); this.renderHero(true); }
          this.loadSessions(false);
        }
      });
    },
    async switchSession(sid) {
      if (sid === this.activeId && this.messages.length) return;
      const d = await api(`/api/chat/sessions/${encodeURIComponent(sid)}`, { silent: true, timeout: 30000 });
      if (!d || d.success === false) { toast((d && d.error) || 'Could not load chat', 'error'); return; }
      this.activeId = sid;
      this.messages = (d.messages || []).map((m) => ({
        id: m.id, role: m.role, content: m.content || '',
        thinking: m.reasoning || '',
        tools: this.parseStoredTools(m.tool_calls),
        model: m.model_used || '',
      }));
      this.renderSessions();
      this.renderMessages();
    },
    parseStoredTools(tc) {
      if (!tc) return [];
      try {
        const arr = typeof tc === 'string' ? JSON.parse(tc) : tc;
        if (!Array.isArray(arr)) return [];
        return arr.map((t) => ({
          title: t.title || t.name || 'tool',
          command: t.command || '',
          status: 'ok', output: [],
        }));
      } catch { return []; }
    },

    /* ── rendering ────────────────────────────────────────────────────── */
    renderHero(show) {
      const hero = $('#chat-hero');
      if (hero) hero.hidden = !show;
    },
    renderMessages() {
      const col = $('#chat-col');
      $$('.msg', col).forEach((m) => m.remove());
      this.renderHero(!this.messages.length);
      for (const m of this.messages) this.renderMessage(m);
      this.scroll();
    },
    md(text) {
      // parts: [text, lang, code, text, lang, code, ...]
      const parts = String(text || '').split(/```(\w*)\n?/);
      let html = '';
      for (let i = 0; i < parts.length; i++) {
        if (i % 3 === 1) continue;                       // language tag
        if (i % 3 === 2) html += `<pre><code>${esc(parts[i])}</code></pre>`;
        else html += this.inlineMd(parts[i]);
      }
      return html;
    },
    inlineMd(text) {
      return esc(text)
        .replace(/`([^`\n]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
        .replace(/^### (.*)$/gm, '<h3>$1</h3>')
        .replace(/^## (.*)$/gm, '<h2>$1</h2>')
        .replace(/^# (.*)$/gm, '<h1>$1</h1>')
        .replace(/^\s*[-*] (.*)$/gm, '<li>$1</li>')
        .replace(/(?:<li>[\s\S]*?<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
        .split(/\n{2,}/).map((p) => (p.trim().startsWith('<') ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)).join('');
    },
    renderMessage(m, { live = false } = {}) {
      const col = $('#chat-col');
      if ($('#chat-hero') && !$('#chat-hero').hidden) this.renderHero(false);
      const el = document.createElement('div');
      el.className = `msg msg-${m.role === 'user' ? 'user' : 'assistant'}`;
      if (live) el.classList.add('streaming');

      const toolsHtml = (m.tools && m.tools.length)
        ? `<div class="msg-tools">${m.tools.map((t, i) => `
            <span class="tool-chip" data-tool="${i}">
              <span class="dot" data-state="${t.status === 'running' ? 'busy' : t.status === 'error' ? 'off' : 'on'}"></span>
              ${esc(t.title)}
            </span>`).join('')}</div>` : '';

      const thinkHtml = (m.thinking && m.thinking.trim())
        ? `<div class="msg-thinking ${live ? 'open' : ''}">
             <div class="msg-thinking-head">
               <span class="dot" data-state="${live ? 'busy' : 'on'}"></span>
               <span>Thinking</span>
               <svg class="t-caret" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
             </div>
             <div class="msg-thinking-body"></div>
           </div>` : '';

      const isUser = m.role === 'user';
      el.innerHTML = `
        <div class="msg-avatar">${isUser ? 'You' : '<img src="/static/iris-logo.png" alt="IRIS" class="avatar-logo">'}</div>
        <div class="msg-body">
          <div class="msg-role">${isUser ? 'You' : 'IRIS'}${m.time ? ` <span class="muted">· ${esc(m.time)}</span>` : ''}</div>
          ${thinkHtml}${toolsHtml}
          <div class="msg-content"></div>
          <div class="msg-error" hidden></div>
        </div>`;
      $('.msg-content', el).innerHTML = isUser
        ? esc(m.content)
        : this.md(m.content || (live ? '' : '…'));
      if (m.error) {
        const errEl = $('.msg-error', el);
        errEl.hidden = false;
        errEl.innerHTML = `${esc(m.error)} <button class="btn btn-secondary btn-sm" data-retry>Retry</button>`;
        $('[data-retry]', errEl).addEventListener('click', () => Chat.send(m.content || ''));
      }
      // thinking panel toggle
      const think = $('.msg-thinking', el);
      if (think) {
        $('.msg-thinking-body', think).textContent = m.thinking || '';
        $('.msg-thinking-head', think).addEventListener('click', () => think.classList.toggle('open'));
      }
      // actions
      if (!live) this.attachActions(el, m);
      col.appendChild(el);
      this.scroll();
      return el;
    },
    attachActions(el, m) {
      const body = $('.msg-body', el);
      const actions = document.createElement('div');
      actions.className = 'msg-actions';
      const mkBtn = (title, svg, fn) => {
        const b = document.createElement('button');
        b.className = 'icon-btn'; b.title = title; b.innerHTML = svg;
        b.addEventListener('click', fn);
        return b;
      };
      const COPY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>';
      const EDIT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';
      const RETRY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6"/></svg>';
      const DEL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>';
      actions.appendChild(mkBtn('Copy', COPY, async () => {
        try { await navigator.clipboard.writeText(m.content || ''); toast('Copied to clipboard.', 'success'); }
        catch { toast('Clipboard is blocked by the browser.', 'warn'); }
      }));
      if (m.role === 'user' && m.id != null) {
        actions.appendChild(mkBtn('Edit', EDIT, () => this.editMessage(el, m)));
      }
      if (m.role === 'assistant' && m.id != null) {
        actions.appendChild(mkBtn('Regenerate', RETRY, () => this.retryMessage(m)));
      }
      if (m.id != null) {
        actions.appendChild(mkBtn('Delete', DEL, () => this.deleteMessage(el, m)));
      }
      body.appendChild(actions);
    },
    scroll() {
      const s = $('#chat-scroll');
      s.scrollTop = s.scrollHeight;
    },

    /* ── message ops: edit / retry / delete ───────────────────────────── */
    async editMessage(el, m) {
      const contentEl = $('.msg-content', el);
      const original = m.content;
      const box = document.createElement('div');
      box.className = 'edit-box';
      box.innerHTML = `
        <textarea class="input"></textarea>
        <div class="edit-actions">
          <button class="btn btn-secondary btn-sm" data-cancel>Cancel</button>
          <button class="btn btn-primary btn-sm" data-save>Save &amp; resend</button>
        </div>`;
      const ta = $('textarea', box);
      ta.value = original;
      contentEl.innerHTML = '';
      contentEl.appendChild(box);
      ta.focus();
      ta.style.height = Math.min(ta.scrollHeight + 4, 240) + 'px';
      $('[data-cancel]', box).addEventListener('click', () => {
        contentEl.innerHTML = esc(original);
      });
      $('[data-save]', box).addEventListener('click', async () => {
        const val = ta.value.trim();
        if (!val || val === original) { contentEl.innerHTML = esc(original); return; }
        if (this.sending) { toast('Stop the current reply first.', 'warn'); return; }
        // 1. persist the edit
        const d = await api(`/api/chat/sessions/${encodeURIComponent(this.activeId)}/messages/${encodeURIComponent(m.id)}`,
          { method: 'PUT', body: { content: val } });
        if (!d || d.success === false) { toast((d && d.error) || 'Edit failed', 'error'); return; }
        m.content = val;
        contentEl.innerHTML = esc(val);
        // 2. delete everything after this message
        const idx = this.messages.findIndex((x) => x.id === m.id);
        for (const later of this.messages.slice(idx + 1)) {
          if (later.id != null) {
            await api(`/api/chat/sessions/${encodeURIComponent(this.activeId)}/messages/${encodeURIComponent(later.id)}`,
              { method: 'DELETE', silent: true });
          }
        }
        this.messages = this.messages.slice(0, idx + 1);
        this.renderMessages();
        // 3. regenerate the assistant reply
        this.streamReply(val, `/api/chat/stream`);
      });
    },
    async retryMessage(m) {
      if (this.sending) { toast('Already generating — stop first.', 'warn'); return; }
      this.streamReply(null, `/api/chat/sessions/${encodeURIComponent(this.activeId)}/retry/${encodeURIComponent(m.id)}`);
    },
    async deleteMessage(el, m) {
      const d = await api(`/api/chat/sessions/${encodeURIComponent(this.activeId)}/messages/${encodeURIComponent(m.id)}`,
        { method: 'DELETE' });
      if (d && d.success) {
        this.messages = this.messages.filter((x) => x.id !== m.id);
        el.remove();
        this.renderHero(!this.messages.length);
        toast('Message deleted.', 'success');
        this.loadSessions(true);
      }
    },

    /* ── sending / streaming ──────────────────────────────────────────── */
    async send(textRaw) {
      const text = String(textRaw ?? $('#chat-input').value).trim();
      if (!text || this.sending) return;
      if (!this.activeId) {
        // auto-create a session on first message
        const sid = uuid();
        await api('/api/chat/sessions', { method: 'POST', silent: true, body: { session_id: sid } });
        this.activeId = sid;
      }
      $('#chat-input').value = '';
      $('#chat-input').style.height = 'auto';
      const userMsg = { id: null, role: 'user', content: text, time: clock() };
      this.messages.push(userMsg);
      this.renderMessage(userMsg);
      this.streamReply(text, '/api/chat/stream');
    },

    /** Stream an assistant reply. `prompt` may be null for retry endpoints. */
    async streamReply(prompt, endpoint) {
      this.sending = true;
      this.setSendingUI(true);
      this.ctrl = new AbortController();

      const live = this.renderMessage(
        { id: null, role: 'assistant', content: '', thinking: '', tools: [], time: clock() },
        { live: true },
      );
      this.liveEl = live;
      this.liveText = '';
      this.liveThinking = '';
      this.liveTools = [];

      const contentEl = $('.msg-content', live);
      const thinkEl = $('.msg-thinking', live);
      const toolsEl = $('.msg-tools', live);
      let phaseEl = null;

      const renderLive = () => {
        contentEl.innerHTML = this.md(this.liveText);
        this.scroll();
      };
      const scheduleRender = () => {
        if (this.renderTimer) return;
        this.renderTimer = setTimeout(() => { this.renderTimer = null; renderLive(); }, 90);
      };

      const body = {
        session_id: this.activeId,
      };
      if (prompt != null) body.message = prompt;

      let errorMsg = null;
      let doneMeta = null;

      try {
        await streamSSE(endpoint, body, (ev) => {
          const type = ev.type;
          if (type === 'phase') {
            if (!phaseEl) {
              phaseEl = document.createElement('div');
              phaseEl.className = 'msg-phase muted';
              phaseEl.style.cssText = 'font-size:12px;margin-bottom:6px';
              $('.msg-body', live).insertBefore(phaseEl, contentEl);
            }
            phaseEl.textContent = `⏳ ${ev.message || ev.phase || ''}`;
          } else if (type === 'answer') {
            this.liveText += ev.content || '';
            if (!phaseEl || this.liveText.length > 0) { if (phaseEl) phaseEl.remove(); phaseEl = null; }
            scheduleRender();
          } else if (type === 'answer_retract') {
            const n = parseInt(ev.length || 0, 10);
            const moved = this.liveText.slice(Math.max(0, this.liveText.length - n));
            this.liveText = this.liveText.slice(0, Math.max(0, this.liveText.length - n));
            this.liveThinking += moved;
            renderLive();
          } else if (type === 'thinking') {
            this.liveThinking += ev.content || '';
            if (thinkEl) {
              $('.msg-thinking-body', thinkEl).textContent = this.liveThinking;
              $('.msg-thinking-body', thinkEl).scrollTop = 1e6;
              thinkEl.classList.add('open');
              this.scroll();
            }
          } else if (type === 'terminal_start') {
            Terminals.spawn(ev.id, ev.title || ev.command || 'action', ev.kind || 'tool', ev.command || '');
            const chip = document.createElement('span');
            chip.className = 'tool-chip';
            chip.dataset.tool = this.liveTools.length;
            chip.innerHTML = `<span class="dot" data-state="busy"></span> ${esc(ev.title || 'action')}`;
            chip.addEventListener('click', () => {
              const t = Terminals.stack.find((x) => x.id === ev.id);
              if (t) { t.el.classList.remove('collapsed'); t.el.scrollIntoView({ behavior: 'smooth', block: 'end' }); }
            });
            let host = $('.msg-tools', live);
            if (!host) {
              host = document.createElement('div');
              host.className = 'msg-tools';
              $('.msg-body', live).insertBefore(host, contentEl);
            }
            host.appendChild(chip);
            this.liveTools.push({ title: ev.title, command: ev.command, status: 'running', chip });
            this.scroll();
          } else if (type === 'terminal_line') {
            Terminals.line(ev.id, ev.line || '', String(ev.line || '').startsWith('ERROR') ? 'err' : '');
          } else if (type === 'terminal_end') {
            Terminals.setStatus(ev.id, ev.status === 'error' ? 'error' : 'ok', ev.summary || '');
            const tool = this.liveTools[this.liveTools.length - 1];
            if (tool) {
              tool.status = ev.status === 'error' ? 'error' : 'ok';
              const dot = tool.chip.querySelector('.dot');
              if (dot) dot.dataset.state = ev.status === 'error' ? 'off' : 'on';
            }
          } else if (type === 'done') {
            doneMeta = ev;
            if (ev.answer && ev.answer.length > this.liveText.length) {
              this.liveText = ev.answer;
            }
          } else if (type === 'error') {
            errorMsg = ev.message || 'The request failed.';
          } else if (type === 'session') {
            if (ev.session_id) this.activeId = ev.session_id;
            if (ev.title) {
              const s = this.sessions.find((x) => x.session_id === ev.session_id);
              if (s) s.title = ev.title;
              else this.loadSessions(true);
              this.renderSessions();
            }
          } else if (type === 'warning') {
            toast(ev.message || '', 'warn', 'Save');
          }
        }, this.ctrl.signal);
      } catch (e) {
        if (e.name !== 'AbortError') errorMsg = e.message;
      }

      // finalize
      if (this.renderTimer) { clearTimeout(this.renderTimer); this.renderTimer = null; }
      live.classList.remove('streaming');
      const phase = $('.msg-phase', live); if (phase) phase.remove();

      const finalMsg = {
        id: null, role: 'assistant',
        content: this.liveText || (errorMsg ? '' : '(no answer)'),
        thinking: this.liveThinking,
        tools: this.liveTools.map((t) => ({ title: t.title, command: t.command, status: t.status, output: [] })),
        time: clock(),
      };
      if (doneMeta && doneMeta.model) finalMsg.model = doneMeta.model;

      // replace the live bubble with a final one (with actions)
      live.remove();
      this.renderMessage(finalMsg);
      if (errorMsg) {
        // surface the error inside the last message
        const lastEl = $('#chat-col').lastElementChild;
        const errEl = $('.msg-error', lastEl);
        if (errEl) {
          errEl.hidden = false;
          errEl.innerHTML = `${esc(errorMsg)}`;
        }
        toast(errorMsg, 'error', 'Chat');
      }
      this.messages.push(finalMsg);

      this.sending = false;
      this.ctrl = null;
      this.setSendingUI(false);
      this.liveEl = null;
      this.loadSessions(true); // refresh titles/counts
    },
    stop() {
      if (this.ctrl) {
        this.ctrl.abort();
        toast('Generation stopped.', 'info');
      }
    },
    setSendingUI(on) {
      $('#chat-send').hidden = on;
      $('#chat-stop').hidden = !on;
      $('#chat-send').disabled = on;
    },
    speak(text) {
      try {
        if (!('speechSynthesis' in window)) return;
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(String(text).slice(0, 600));
        u.lang = navigator.language || 'en-US';
        speechSynthesis.speak(u);
      } catch { /* TTS best-effort */ }
    },
  };

  function initChat() {
    const input = $('#chat-input');
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 180) + 'px';
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); Chat.send(); }
    });
    $('#chat-send').addEventListener('click', () => Chat.send());
    $('#chat-stop').addEventListener('click', () => Chat.stop());
    $('#chat-mic').addEventListener('click', () => Voice.open());
    $('#new-chat').addEventListener('click', () => Chat.newSession());
    $$('.chip.suggest').forEach((c) => c.addEventListener('click', () => {
      navigate('chat');
      Chat.send(c.dataset.suggest);
    }));
    Chat.loadSessions(false).then(() => {
      if (Chat.sessions.length) Chat.switchSession(Chat.activeId);
    });
  }

  /* ── Voice (browser speech recognition) ─────────────────────────────── */
  const Voice = {
    rec: null, listening: false, finalText: '',
    supported() { return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window; },
    open() {
      if (!this.supported()) { toast('This browser has no speech recognition. Chrome or Edge support it.', 'error', 'Voice unavailable'); return; }
      $('#voice-pop').hidden = false;
    },
    close() { this.stop(); $('#voice-pop').hidden = true; },
    setState(state, text) {
      $('#voice-dot').dataset.state = state;
      $('#voice-state-label').textContent = text;
    },
    start() {
      if (this.listening) { this.stop(); return; }
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.rec = new Ctor();
      this.rec.continuous = true;
      this.rec.interimResults = true;
      this.rec.lang = navigator.language || 'en-US';
      this.finalText = '';
      $('#voice-text').textContent = 'Listening… speak now.';
      this.rec.onresult = (ev) => {
        let interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          if (ev.results[i].isFinal) this.finalText += ev.results[i][0].transcript;
          else interim += ev.results[i][0].transcript;
        }
        $('#voice-text').textContent = this.finalText + interim;
      };
      this.rec.onerror = (ev) => {
        if (ev.error === 'not-allowed') toast('Microphone permission denied.', 'error', 'Voice');
        this.stop();
      };
      this.rec.onend = () => { this.listening = false; this.setState('off', 'Voice'); };
      this.rec.start();
      this.listening = true;
      this.setState('busy', 'Listening…');
      $('#voice-start').textContent = 'Stop';
      $('#voice-send-chat').disabled = false;
    },
    stop() {
      if (this.rec && this.listening) { try { this.rec.stop(); } catch { /* noop */ } }
      this.listening = false;
      this.setState('off', 'Voice');
      $('#voice-start').textContent = 'Start listening';
    },
    sendToChat() {
      const t = $('#voice-text').textContent;
      this.close();
      navigate('chat');
      if (t && !t.startsWith('Listening') && !t.startsWith('Use the browser')) Chat.send(t.trim());
    },
  };
  $('#voice-btn').addEventListener('click', () => Voice.open());
  $('#voice-close').addEventListener('click', () => Voice.close());
  $('#voice-start').addEventListener('click', () => Voice.start());
  $('#voice-send-chat').addEventListener('click', () => Voice.sendToChat());

  /* ── Sidebar behavior ───────────────────────────────────────────────── */
  function closeSidebar() {
    if (window.innerWidth <= 980) {
      $('#sidebar').classList.remove('open');
      $('#scrim').hidden = true;
    }
  }
  function initSidebar() {
    $('#menu-btn').addEventListener('click', () => {
      $('#sidebar').classList.add('open');
      $('#scrim').hidden = false;
    });
    $('#scrim').addEventListener('click', closeSidebar);
    $('#sidebar-collapse').addEventListener('click', () => {
      const app = $('#app');
      app.classList.toggle('chatlist-hidden');
      const hidden = app.classList.contains('chatlist-hidden');
      $('#chats-btn').hidden = !hidden;
      try { localStorage.setItem('iris-sidebar-collapsed', hidden ? '1' : '0'); } catch { /* ignore */ }
    });
    $('#chats-btn').addEventListener('click', () => {
      $('#app').classList.remove('chatlist-hidden');
      $('#chats-btn').hidden = true;
      try { localStorage.setItem('iris-sidebar-collapsed', '0'); } catch { /* ignore */ }
    });
    try {
      if (localStorage.getItem('iris-sidebar-collapsed') === '1') {
        $('#app').classList.add('chatlist-hidden');
        $('#chats-btn').hidden = false;
      }
    } catch { /* ignore */ }
  }

  /* ══════════════════════════════════════════════════════════════════════
     AGENTS — registry, delegation with rising terminals
     ══════════════════════════════════════════════════════════════════════ */
  const Agents = {
    list: [], filter: '', tabs: [], activeTab: null, seq: 0,
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
      renderAgentList();
      const badge = $('#agents-count');
      badge.textContent = `${Agents.list.length} ready`;
      badge.className = 'badge accent';
    } catch (e) {
      listEl.innerHTML = `<div class="empty-state">The registry could not be loaded.<br>${esc(e.message)}<br><br>
        <button class="btn btn-secondary btn-sm" onclick="location.reload()">Retry</button></div>`;
      $('#agents-count').textContent = 'unavailable';
      $('#agents-count').className = 'badge err';
    }
  }
  function renderAgentList() {
    const q = Agents.filter.toLowerCase();
    const list = Agents.list.filter((a) => {
      const name = String(a.name || '').toLowerCase();
      const codename = String(a.codename || '').toLowerCase();
      const skills = (a.specialties || []).join(' ').toLowerCase();
      return !q || name.includes(q) || codename.includes(q) || skills.includes(q);
    });
    const el = $('#agent-list');
    if (!list.length) { el.innerHTML = '<div class="empty-state">No agents match this filter.</div>'; return; }
    el.innerHTML = '';
    for (const a of list) {
      const card = document.createElement('div');
      card.className = 'agent-card';
      const skills = (a.specialties || []).slice(0, 3);
      card.innerHTML = `
        <div class="agent-top">
          <span class="agent-name">${esc(a.codename || a.name)}</span>
          <span class="agent-class">${esc(a.name)}</span>
        </div>
        <div class="agent-skills">${skills.map((s) => `<span class="skill-tag">${esc(s)}</span>`).join('') ||
          '<span class="skill-tag">general</span>'}</div>
        <div class="roster-cta">
          <button class="btn btn-primary btn-sm" data-delegate>Delegate task</button>
          <button class="btn btn-secondary btn-sm" data-inspect>Details</button>
        </div>`;
      card.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-delegate]')) { openDelegateModal(a); return; }
        if (ev.target.closest('[data-inspect]')) {
          const info = document.createElement('div');
          info.innerHTML = `<div class="kv-list">${
            Object.entries({ id: a.name, codename: a.codename, class: a.class, delegatable: a.delegatable, specialties: (a.specialties || []).join(', ') })
              .map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join('')
          }</div>`;
          Modal.open(`Agent · ${a.codename || a.name}`, info);
          return;
        }
        $$('.agent-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        openDelegateModal(a);
      });
      el.appendChild(card);
    }
  }
  function openDelegateModal(agent, presetTask) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <p class="muted" style="font-size:12.5px">Task for <strong>${esc(agent.codename || agent.name)}</strong> — the agent runs it for real; a rising terminal shows its live output.</p>
      <textarea class="input" rows="4" data-task placeholder="Describe the task precisely… include any target URL or domain">${esc(presetTask || '')}</textarea>
      <div class="form-row"><button class="btn btn-primary" data-run>Run task</button></div>`;
    const run = async () => {
      const task = $('[data-task]', wrap).value.trim();
      if (!task) { toast('Describe the task first.', 'warn'); return; }
      Modal.close();
      await runDelegation(agent, task);
    };
    $('[data-run]', wrap).onclick = run;
    $('[data-task]', wrap).addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run();
    });
    Modal.open('Delegate to agent', wrap);
  }
  async function runDelegation(agent, task) {
    const id = `t${++Agents.seq}`;
    const termId = `agent_${id}_${Date.now()}`;
    const agentName = agent.codename || agent.name;
    Agents.tabs.push({ id, agent: agentName, task, status: 'running', started: Date.now(), out: '' });
    updateAgentsBadge();
    renderTabs();
    switchTab(id);
    // rising terminal for the live run
    Terminals.spawn(termId, `AGENT · ${String(agentName).toUpperCase()}`, 'agent', `delegate → ${agent.name}: ${task}`);
    try {
      const d = await api('/api/omnis/delegate', {
        method: 'POST', timeout: 300000,
        body: { agent: agent.name, task: { description: task, request: task } },
      });
      const tab = Agents.tabs.find((t) => t.id === id);
      if (!tab) return;
      const out = formatDelegation(d);
      tab.out = out;
      tab.status = (d && d.success === false) ? 'failed' : 'done';
      // stream result into the rising terminal
      for (const line of out.split('\n').slice(0, 200)) Terminals.line(termId, line);
      Terminals.setStatus(termId, tab.status === 'done' ? 'ok' : 'error',
        `${tab.status === 'done' ? 'completed' : 'failed'} · ${d && d.execution_time ? d.execution_time + 's' : ''}`);
    } catch (e) {
      const tab = Agents.tabs.find((t) => t.id === id);
      if (tab) { tab.status = 'failed'; tab.out = `Request failed:\n${e.message}`; }
      Terminals.line(termId, `ERROR: ${e.message}`);
      Terminals.setStatus(termId, 'error');
    }
    renderTabs();
    updateAgentsBadge();
    loadActivity();
  }
  function formatDelegation(d) {
    if (d == null) return '(no output)';
    if (d && d.success === false && d.error) return `The agent reported an error:\n${d.error}`;
    const pick = d.output ?? d.result ?? d.response ?? d.message;
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
    strip.innerHTML = Agents.tabs.map((t) => `
      <div class="agent-tab ${t.id === Agents.activeTab ? 'active' : ''}" role="tab" data-tab="${t.id}">
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
    panels.innerHTML = `
      <div class="task-head">
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
        ? 'Working… the agent is executing this task on the server. Watch the rising terminal for live output.'
        : esc(t.out)}</div>`;
    $('[data-rerun]', panels).addEventListener('click', () => {
      const a = Agents.list.find((x) => (x.codename || x.name) === t.agent) || { name: t.agent, codename: t.agent };
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
      if (!log.length) {
        ol.innerHTML = '<li class="empty-state" style="border:none;padding:8px">No executions recorded yet.</li>';
      } else {
        ol.innerHTML = log.slice(0, 20).map((e) => {
          const cap = e.capability || e.action || 'execution';
          const ok = e.success !== false;
          const ts = e.timestamp ? fmtTime(e.timestamp) : '';
          return `<li><strong>${esc(cap)}</strong> ${ok ? '✓' : '✗'} ${esc(String(e.error || e.result || '')) .slice(0, 120)} <span class="muted">${esc(ts)}</span></li>`;
        }).join('');
      }
    } catch (e) {
      $('#omnis-meta').textContent = `OMNIS status unavailable — ${e.message}`;
    }
  }
  function initAgents() {
    $('#agent-search').addEventListener('input', (e) => { Agents.filter = e.target.value; renderAgentList(); });
    $('#omnis-refresh').addEventListener('click', loadAgentsView);
  }

  /* ══════════════════════════════════════════════════════════════════════
     APPS
     ══════════════════════════════════════════════════════════════════════ */
  async function setBadge(id, fn) {
    try {
      const n = await fn();
      const el = $(id);
      if (el) { el.hidden = !(n > 0); el.textContent = n > 99 ? '99+' : n; }
    } catch { /* badge silent */ }
  }
  function loadAppsHub() {
    setBadge('#app-badge-notes', async () => (await api('/api/notes', { silent: true })).notes?.length || 0);
    setBadge('#app-badge-calendar', async () => (await api('/api/calendar/upcoming', { silent: true })).events?.length || 0);
    setBadge('#app-badge-projects', async () => (await api('/api/projects', { silent: true })).projects?.length || 0);
    setBadge('#app-badge-phone', async () => ((await api('/api/phone/device-info', { silent: true })).connected ? 1 : 0));
    setBadge('#badge-notes', async () => (await api('/api/notes', { silent: true })).notes?.length || 0);
    setBadge('#badge-calendar', async () => (await api('/api/calendar/upcoming', { silent: true })).events?.length || 0);
  }

  /* ── Calendar ─────────────────────────────────────────────────────── */
  const Cal = { month: new Date(), events: [], selected: null };
  async function loadCalendar() {
    try {
      const y = Cal.month.getFullYear(); const m = Cal.month.getMonth();
      const start = new Date(y, m, 1).toISOString().slice(0, 10);
      const end = new Date(y, m + 1, 0).toISOString().slice(0, 10);
      const d = must(await api(`/api/calendar/events?start=${start}&end=${end}`, { silent: true }), 'Calendar');
      Cal.events = d.events || [];
      $('#cal-month-label').textContent = Cal.month.toLocaleDateString([], { month: 'long', year: 'numeric' });
      renderCalGrid();
      loadUpcoming();
      renderCalDay(Cal.selected || new Date());
    } catch (e) {
      $('#cal-grid').innerHTML = `<div class="empty-state">Calendar unavailable — ${esc(e.message)}</div>`;
      warnConsole('#cal-day-list', e.message);
    }
  }
  function renderCalGrid() {
    const y = Cal.month.getFullYear(); const m = Cal.month.getMonth();
    const first = new Date(y, m, 1);
    const offset = (first.getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const daysPrev = new Date(y, m, 0).getDate();
    const cells = [];
    for (let i = offset; i > 0; i--) cells.push({ d: daysPrev - i + 1, other: true, date: new Date(y, m - 1, daysPrev - i + 1) });
    for (let d = 1; d <= daysInMonth; d++) cells.push({ d, other: false, date: new Date(y, m, d) });
    while (cells.length % 7 !== 0 || cells.length < 42) {
      const dd = cells.length - offset - daysInMonth + 1;
      cells.push({ d: dd, other: true, date: new Date(y, m + 1, dd) });
      if (cells.length >= 42) break;
    }
    const today = new Date();
    const grid = $('#cal-grid');
    grid.innerHTML = '';
    for (const c of cells.slice(0, 42)) {
      const ds = `${c.date.getFullYear()}-${String(c.date.getMonth() + 1).padStart(2, '0')}-${String(c.date.getDate()).padStart(2, '0')}`;
      const evs = Cal.events.filter((e) => String(e.start_time || '').startsWith(ds));
      const el = document.createElement('div');
      el.className = `cal-day ${c.other ? 'other' : ''} ${ds === today.toISOString().slice(0, 10) ? 'today' : ''} ${Cal.selected && ds === Cal.selected.toISOString().slice(0, 10) ? 'selected' : ''}`;
      el.innerHTML = `<span class="cd-num">${c.d}</span>
        <span class="cd-events">${evs.slice(0, 2).map((e) => `<span class="cd-ev">${esc(e.title)}</span>`).join('')}
        ${evs.length > 2 ? `<span class="cd-ev">+${evs.length - 2} more</span>` : ''}</span>`;
      el.addEventListener('click', () => { Cal.selected = c.date; renderCalGrid(); renderCalDay(c.date); });
      grid.appendChild(el);
    }
  }
  function renderCalDay(date) {
    const ds = date.toISOString().slice(0, 10);
    const evs = Cal.events.filter((e) => String(e.start_time || '').startsWith(ds));
    $('#cal-day-title').textContent = date.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
    const list = $('#cal-day-list');
    if (!evs.length) { list.innerHTML = '<div class="empty-state">Nothing scheduled.</div>'; return; }
    list.innerHTML = '';
    evs.forEach((ev) => list.appendChild(eventRow(ev)));
  }
  async function loadUpcoming() {
    try {
      const d = must(await api('/api/calendar/upcoming', { silent: true }), 'Upcoming');
      const list = $('#cal-upcoming-list');
      const evs = d.events || [];
      if (!evs.length) { list.innerHTML = '<div class="empty-state">Nothing in the next 24 hours.</div>'; return; }
      list.innerHTML = '';
      evs.forEach((ev) => list.appendChild(eventRow(ev)));
    } catch (e) { warnConsole('#cal-upcoming-list', e.message); }
  }
  function eventRow(ev) {
    const el = document.createElement('div');
    el.className = 'cal-event';
    el.innerHTML = `<div>
        <div class="ce-title">${esc(ev.title)}</div>
        <div class="ce-time">${esc(fmtTime(ev.start_time))}${ev.end_time ? ' → ' + esc(fmtTime(ev.end_time)) : ''}</div>
      </div>
      <button class="icon-btn ce-del" title="Delete">🗑</button>`;
    $('.ce-del', el).addEventListener('click', async () => {
      must(await api(`/api/calendar/events/${encodeURIComponent(ev.id || ev.event_id)}`, { method: 'DELETE' }), 'Delete event');
      toast('Event deleted.', 'success');
      loadCalendar();
    });
    return el;
  }
  function openEventModal(date) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <div class="ev-form">
        <label class="field"><span>Title</span><input class="input" data-title placeholder="Team sync"></label>
        <label class="field"><span>Start (date + time)</span><input class="input" data-start type="datetime-local"></label>
        <label class="field"><span>End (optional)</span><input class="input" data-end type="datetime-local"></label>
        <label class="field"><span>Location (optional)</span><input class="input" data-loc></label>
        <div class="form-row end">
          <button class="btn btn-primary" data-add>Add event</button>
        </div>
      </div>`;
    if (date) {
      const ds = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
      $('[data-start]', wrap).value = `${ds}T09:00`;
    }
    $('[data-add]', wrap).addEventListener('click', async () => {
      const title = $('[data-title]', wrap).value.trim();
      const start = $('[data-start]', wrap).value;
      if (!title || !start) { toast('Title and start time are required.', 'warn'); return; }
      must(await api('/api/calendar/events', { method: 'POST', body: {
        title, start_time: start, end_time: $('[data-end]', wrap).value || null, location: $('[data-loc]', wrap).value || null,
      } }), 'Create event');
      Modal.close();
      toast('Event created.', 'success');
      loadCalendar();
    });
    Modal.open('Add event', wrap);
  }
  function initCalendarApp() {
    $('#cal-prev').addEventListener('click', () => { Cal.month = new Date(Cal.month.getFullYear(), Cal.month.getMonth() - 1, 1); loadCalendar(); });
    $('#cal-next').addEventListener('click', () => { Cal.month = new Date(Cal.month.getFullYear(), Cal.month.getMonth() + 1, 1); loadCalendar(); });
    $('#cal-today').addEventListener('click', () => { Cal.month = new Date(); Cal.selected = new Date(); loadCalendar(); });
    $('#cal-add').addEventListener('click', () => openEventModal(Cal.selected));
    $('#cal-export').addEventListener('click', () => {
      const ics = Cal.events.map((e) => [
        'BEGIN:VEVENT', `SUMMARY:${(e.title || '').replace(/,/g, '\\,')}`,
        `DTSTART:${String(e.start_time || '').replace(/[-:]/g, '')}`,
        e.end_time ? `DTEND:${String(e.end_time).replace(/[-:]/g, '')}` : '',
        'END:VEVENT'].filter(Boolean).join('\r\n')).join('\r\n');
      const blob = new Blob([`BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//IRIS//Calendar//EN\r\n${ics}\r\nEND:VCALENDAR`], { type: 'text/calendar' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'iris-calendar.ics';
      a.click();
      toast('Calendar exported.', 'success');
    });
  }

  /* ── Notes ────────────────────────────────────────────────────────── */
  const Notes = { list: [], activeId: null };
  async function loadNotes() {
    try {
      const d = must(await api(`/api/notes${ $('#notes-search').value.trim() ? `?search=${encodeURIComponent($('#notes-search').value.trim())}` : ''}`, { silent: true }), 'Notes');
      Notes.list = d.notes || [];
      renderNotesList();
    } catch (e) {
      $('#notes-list').innerHTML = `<div class="empty-state">Notes unavailable — ${esc(e.message)}</div>`;
    }
  }
  function renderNotesList() {
    const el = $('#notes-list');
    if (!Notes.list.length) { el.innerHTML = '<div class="empty-state">No notes found.</div>'; return; }
    el.innerHTML = '';
    for (const n of Notes.list) {
      const item = document.createElement('div');
      item.className = `note-item ${n.id === Notes.activeId ? 'active' : ''}`;
      item.innerHTML = `
        <div class="ni-title">${n.pinned ? '<span class="ni-pin">📌</span> ' : ''}${esc(n.title || 'Untitled')}</div>
        <div class="ni-meta"><span>${esc(n.category || 'general')}</span>·<span>${fmtTime(n.updated_at || n.created_at)}</span></div>`;
      item.addEventListener('click', () => selectNote(n.id));
      el.appendChild(item);
    }
  }
  async function selectNote(id) {
    const n = Notes.list.find((x) => x.id === id);
    if (!n) return;
    Notes.activeId = id;
    renderNotesList();
    $('#editor-empty').hidden = true;
    $('#editor-body').hidden = false;
    $('#note-title').value = n.title || '';
    $('#note-category').value = n.category || '';
    $('#note-tags').value = (n.tags || []).join(', ');
    $('#note-content').value = n.content || '';
    $('#note-meta').textContent = `Updated ${fmtTime(n.updated_at || n.created_at)}`;
    $('#note-pin').textContent = n.pinned ? 'Unpin' : 'Pin';
  }
  function initNotes() {
    let t = null;
    $('#notes-search').addEventListener('input', () => {
      clearTimeout(t); t = setTimeout(loadNotes, 260);
    });
    $('#note-new').addEventListener('click', async () => {
      const d = must(await api('/api/notes', { method: 'POST', body: { title: 'Untitled note', content: '' } }), 'New note');
      await loadNotes();
      selectNote(d.note.id);
      $('#note-title').focus();
      $('#note-title').select();
    });
    $('#note-save').addEventListener('click', async () => {
      if (!Notes.activeId) return;
      must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}`, { method: 'PUT', body: {
        title: $('#note-title').value, content: $('#note-content').value,
        category: $('#note-category').value || 'general',
        tags: $('#note-tags').value.split(',').map((s) => s.trim()).filter(Boolean),
      } }), 'Save note');
      toast('Note saved.', 'success');
      loadNotes();
    });
    $('#note-pin').addEventListener('click', async () => {
      const n = Notes.list.find((x) => x.id === Notes.activeId);
      must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}/pin`, { method: 'POST', body: { pinned: !(n && n.pinned) } }), 'Pin note');
      loadNotes().then(() => selectNote(Notes.activeId));
    });
    $('#note-delete').addEventListener('click', async () => {
      must(await api(`/api/notes/${encodeURIComponent(Notes.activeId)}`, { method: 'DELETE' }), 'Delete note');
      toast('Note deleted.', 'success');
      Notes.activeId = null;
      $('#editor-body').hidden = true;
      $('#editor-empty').hidden = false;
      loadNotes();
    });
  }

  /* ── Calculator (standard + scientific + statistics) ─────────────── */
  const Calc = {
    expr: '', history: [],
    load() { try { this.history = JSON.parse(localStorage.getItem('iris-calc-history') || '[]'); } catch { this.history = []; } this.paintHistory(); },
    persist() { try { localStorage.setItem('iris-calc-history', JSON.stringify(this.history.slice(-40))); } catch { /* quota */ } },
    press(k) {
      if (k === 'C') this.expr = '';
      else if (k === '⌫') this.expr = this.expr.slice(0, -1);
      else if (k === '±') this.expr = this.expr.startsWith('−') ? this.expr.slice(1) : '−' + this.expr;
      else if (k === '=') return this.equals();
      else this.expr += k;
      this.paint();
    },
    equals() {
      if (!this.expr.trim()) return;
      try {
        const val = this.evaluate(this.expr);
        if (val === undefined || val === null || Number.isNaN(val)) throw new Error('not a number');
        this.history.push({ expr: this.expr, val: String(val) });
        this.persist();
        this.expr = String(val);
        this.paint(); this.paintHistory();
      } catch (e) {
        toast(`Could not evaluate “${this.expr}” — ${e.message}`, 'warn', 'Calculator');
      }
    },
    evaluate(src) {
      const js = src.replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-')
        .replace(/(\d+)%/g, '($1/100)');
      if (!/^[0-9+\-*/().%\s]*$/.test(js)) throw new Error('invalid characters');
      // eslint-disable-next-line no-new-func
      const val = Function(`"use strict"; return (${js})`)();
      if (typeof val !== 'number' || !isFinite(val)) throw new Error('not finite');
      return Math.round(val * 1e10) / 1e10;
    },
    paint() {
      $('#calc-expr').textContent = this.expr || '\u00a0';
      try {
        if (this.expr && /^[0-9+\-*/().%\s×÷−]+$/.test(this.expr)) {
          const v = this.evaluate(this.expr);
          $('#calc-result').textContent = String(v);
        } else {
          $('#calc-result').textContent = this.expr ? '…' : '0';
        }
      } catch { $('#calc-result').textContent = '…'; }
    },
    paintHistory() {
      const el = $('#calc-history');
      if (!this.history.length) { el.innerHTML = '<li class="empty-state">No calculations yet.</li>'; return; }
      el.innerHTML = '';
      for (const h of this.history.slice().reverse()) {
        const li = document.createElement('li');
        li.innerHTML = `<span class="h-expr">${esc(h.expr)}</span><span class="h-val">${esc(h.val)}</span>`;
        li.addEventListener('click', () => { Calc.expr = h.expr; Calc.paint(); });
        el.appendChild(li);
      }
    },
  };
  function initCalculator() {
    Calc.load();
    $('#calc-keypad').addEventListener('click', (e) => {
      const k = e.target.closest('[data-k]');
      if (k) Calc.press(k.dataset.k);
    });
    $('#calc-clear-history').addEventListener('click', () => { Calc.history = []; Calc.persist(); Calc.paintHistory(); });
    document.addEventListener('keydown', (e) => {
      if (currentRoute() !== 'apps/calculator' || !$('#calc-standard') || !$('#calc-standard').offsetParent) return;
      if (e.target.matches('input, textarea, select')) return;
      const map = { '*': '×', '/': '÷', '-': '−', '+': '+', '(': '(', ')': ')', '%': '%', '.': '.', Enter: '=', Backspace: '⌫', Escape: 'C' };
      if (/^\d$/.test(e.key)) { Calc.press(e.key); e.preventDefault(); }
      else if (map[e.key]) { Calc.press(map[e.key]); e.preventDefault(); }
    });
    // tabs
    $$('.calc-tabs .chip').forEach((tab) => tab.addEventListener('click', () => {
      $$('.calc-tabs .chip').forEach((c) => c.classList.toggle('active', c === tab));
      $$('.calc-pane').forEach((p) => { p.hidden = p.id !== `calc-${tab.dataset.calcTab}`; });
    }));
    // scientific (sympy backend)
    $('#math-ops').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-op]');
      if (!btn) return;
      const op = btn.dataset.op;
      const expr = $('#math-expression').value.trim();
      if (!expr) { toast('Enter an expression first.', 'warn', 'Math'); return; }
      const body = { expression: expr, variable: $('#math-var').value.trim() || 'x', order: $('#math-order').value || 1 };
      if (op === 'integrate') body.limits = $('#math-limits').value.trim() || null;
      const d = await api(`/api/math/${op === 'evaluate' ? 'evaluate' : op}`, { method: 'POST', body, timeout: 30000 });
      const out = $('#math-output');
      out.hidden = false;
      out.textContent = d && d.success === false ? `Error: ${d.error}` : JSON.stringify(d, null, 2);
    });
    // statistics
    $('#stats-compute').addEventListener('click', async () => {
      const raw = $('#stats-input').value.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean).map(Number);
      if (!raw.length || raw.some(Number.isNaN)) { toast('Enter numbers only (one per line or comma separated).', 'warn', 'Statistics'); return; }
      const d = await api('/api/math/statistics', { method: 'POST', body: { values: raw } });
      const grid = $('#stats-output');
      if (!d || d.success === false) { toast((d && d.error) || 'Statistics failed', 'error'); return; }
      grid.hidden = false;
      const cells = [['count', d.count], ['mean', d.mean], ['median', d.median], ['stdev', d.stdev],
        ['variance', d.variance], ['min', d.min], ['max', d.max], ['sum', d.sum]];
      grid.innerHTML = cells.filter(([k, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `<div class="stat-cell"><div class="s-k">${esc(k)}</div><div class="s-v">${esc(String(Math.round(v * 1e6) / 1e6))}</div></div>`).join('');
    });
  }

  /* ── Projects ─────────────────────────────────────────────────────── */
  async function loadProjects() {
    try {
      const t = await api('/api/projects/templates', { silent: true });
      const templates = t.templates || [];
      const entries = Array.isArray(templates) ? templates : Object.entries(templates);
      const sel = $('#project-template');
      sel.innerHTML = entries.map(([id, desc]) =>
        `<option value="${esc(id)}">${esc(id)} — ${esc(String(desc).slice(0, 60))}</option>`).join('');
      $('#projects-templates-badge').textContent = `${entries.length} templates`;
      $('#projects-templates-badge').className = 'badge accent';
    } catch (e) {
      $('#project-template').innerHTML = '<option value="">unavailable</option>';
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
          <div class="p-meta">${esc([p.template, p.status, p.path, p.created_at && fmtTime(p.created_at)].filter(Boolean).join(' · '))}</div>`;
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
      btn.disabled = true;
      const out = $('#project-output');
      out.hidden = true;
      try {
        const d = must(await api('/api/projects/generate', { method: 'POST', timeout: 300000, body: { name, template: template.split(' — ')[0], description } }), 'Generate project');
        out.hidden = false;
        out.textContent = JSON.stringify(d, null, 2).slice(0, 4000);
        toast(`Project “${name}” generated.`, 'success');
        loadProjects();
      } catch (err) {
        out.hidden = false;
        out.textContent = `Failed: ${err.message}`;
      } finally { btn.disabled = false; }
    });
  }

  /* ── Vision ───────────────────────────────────────────────────────── */
  const Vision = { stream: null, active: false };
  function setVisionState(text, cls = '') {
    const b = $('#vision-state');
    b.textContent = text;
    b.className = `badge ${cls}`;
  }
  async function startVision() {
    if (!navigator.mediaDevices) { toast('This browser does not expose media capture APIs.', 'error', 'Vision unavailable'); return; }
    const source = $('#vision-source').value;
    try {
      Vision.stream = source === 'screen'
        ? await navigator.mediaDevices.getDisplayMedia({ video: true })
        : await navigator.mediaDevices.getUserMedia({ video: true });
      Vision.active = true;
      $('#vision-video').srcObject = Vision.stream;
      $('#vision-video').hidden = false;
      $('#vision-placeholder').hidden = true;
      $('#vision-start').disabled = true;
      $('#vision-stop').disabled = false;
      setVisionState(`streaming · ${source === 'screen' ? 'screen' : 'camera'}`, 'accent');
      Vision.stream.getVideoTracks()[0].addEventListener('ended', stopVision);
      toast(`${source === 'screen' ? 'Screen' : 'Camera'} stream is live.`, 'success');
    } catch (e) {
      if (e.name === 'NotAllowedError') toast('Permission denied — allow the screen/camera pick to start.', 'warn', 'Stream cancelled');
      else toast(e.message || String(e), 'error', 'Stream failed');
    }
  }
  function stopVision(browserEnded = false) {
    if (Vision.stream) Vision.stream.getTracks().forEach((t) => t.stop());
    Vision.stream = null; Vision.active = false;
    $('#vision-video').srcObject = null;
    $('#vision-video').hidden = true;
    $('#vision-placeholder').hidden = false;
    $('#vision-start').disabled = false;
    $('#vision-stop').disabled = true;
    setVisionState('idle');
    if (!browserEnded) toast('Stream stopped.', 'info');
  }
  function captureFrame() {
    const video = $('#vision-video');
    if (!Vision.active || !video.videoWidth) throw new Error('No live stream — start it first.');
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1280 / video.videoWidth);
    canvas.width = video.videoWidth * scale;
    canvas.height = video.videoHeight * scale;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
  }
  function initVision() {
    $('#vision-start').addEventListener('click', startVision);
    $('#vision-stop').addEventListener('click', () => stopVision());
    $('#vision-analyze').addEventListener('click', async () => {
      try {
        const image = captureFrame();
        const question = $('#vision-question').value.trim() || 'What do you see?';
        const out = $('#vision-output');
        out.hidden = false;
        out.textContent = 'Analyzing frame…';
        const d = await api('/api/vision/analyze', { method: 'POST', timeout: 120000, body: { image, question } });
        out.textContent = (d && (d.analysis || d.description || d.response)) || JSON.stringify(d, null, 2);
      } catch (e) {
        toast(`Frame capture failed: ${e.message}`, 'error', 'Vision');
      }
    });
    // transcription
    let rec = null; let listening = false; let finalText = '';
    const setState = (s) => { $('#transcript-state').textContent = s; };
    $('#transcript-toggle').addEventListener('click', () => {
      if (listening) { try { rec.stop(); } catch { /* noop */ } return; }
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Ctor) { toast('This browser has no speech recognition.', 'error', 'Transcription unavailable'); return; }
      rec = new Ctor(); rec.continuous = true; rec.interimResults = true;
      rec.lang = navigator.language || 'en-US';
      finalText = '';
      $('#transcript-box').innerHTML = '';
      $('#transcript-empty').hidden = true;
      $('#transcript-ask').disabled = false;
      rec.onresult = (ev) => {
        let interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          if (ev.results[i].isFinal) finalText += ev.results[i][0].transcript + '\n';
          else interim += ev.results[i][0].transcript;
        }
        $('#transcript-box').innerHTML = `${esc(finalText)}<span class="interim">${esc(interim)}</span>`;
      };
      rec.onerror = (ev) => { if (ev.error === 'not-allowed') toast('Microphone permission denied.', 'error', 'Mic blocked'); };
      rec.onend = () => { listening = false; setState('off'); $('#transcript-toggle').textContent = 'Listen'; };
      rec.start();
      listening = true;
      setState('listening');
      $('#transcript-toggle').textContent = 'Stop';
    });
    $('#transcript-clear').addEventListener('click', () => {
      finalText = '';
      $('#transcript-box').innerHTML = '<div class="empty-state" id="transcript-empty">No transcript yet. Press “Listen” and speak.</div>';
      $('#transcript-ask').disabled = true;
    });
    $('#transcript-ask').addEventListener('click', () => {
      const text = finalText.trim();
      if (!text) { toast('No transcript yet.', 'warn'); return; }
      navigate('chat');
      let q = `Here is what I just said: "${text.slice(0, 800)}"`;
      try { if (Vision.active) q += ' — I am sharing my screen, analyze it too.'; } catch { /* noop */ }
      Chat.send(q);
    });
  }

  /* ── Phone (ADB bridge) ───────────────────────────────────────────── */
  async function loadPhone() {
    try {
      const d = await api('/api/phone/device-info', { silent: true, timeout: 20000 });
      const kv = $('#phone-device-info');
      $('#phone-state').textContent = d && d.connected ? 'connected' : 'disconnected';
      $('#phone-state').className = `badge ${d && d.connected ? 'ok' : 'warn'}`;
      const entries = Object.entries(d || {}).filter(([k]) => k !== 'success');
      kv.innerHTML = entries.length
        ? entries.map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</span></div>`).join('')
        : '<div class="empty-state">No device info — is ADB running?</div>';
    } catch (e) {
      $('#phone-state').textContent = 'unreachable';
      $('#phone-state').className = 'badge err';
    }
  }
  function initPhone() {
    loadPhone();
    $('#phone-ask-iris').addEventListener('click', () => {
      const cmd = $('#adb-cmd').value.trim();
      if (!cmd) { toast('Type an adb command first.', 'warn'); return; }
      navigate('chat');
      Chat.send(`Run on my phone: adb ${cmd}`);
    });
    $('#adb-run').addEventListener('click', async () => {
      const cmd = $('#adb-cmd').value.trim();
      if (!cmd) return;
      const out = $('#adb-exec-out');
      out.hidden = false;
      out.textContent = `$ adb ${cmd}\n…`;
      const d = await api('/api/phone/exec', { method: 'POST', timeout: 60000, body: { command: cmd } });
      out.textContent = `$ adb ${cmd}\n${(d && (d.output || d.stdout)) || JSON.stringify(d, null, 2)}`;
    });
    $('#adb-quick').addEventListener('click', (e) => {
      const chip = e.target.closest('[data-cmd]');
      if (chip) { $('#adb-cmd').value = chip.dataset.cmd; $('#adb-run').click(); }
    });
    $('#adb-scan').addEventListener('click', async () => {
      const out = $('#adb-devices-out');
      out.hidden = false;
      out.textContent = 'scanning…';
      const d = await api('/api/phone/devices', { timeout: 30000 });
      out.textContent = JSON.stringify(d, null, 2);
    });
    $('#adb-connect').addEventListener('click', async () => {
      const address = $('#adb-address').value.trim();
      if (!address) { toast('Enter an IP:port first.', 'warn'); return; }
      const out = $('#adb-connect-out');
      out.hidden = false;
      out.textContent = 'connecting…';
      const d = await api('/api/phone/connect', { method: 'POST', timeout: 30000, body: { address } });
      out.textContent = JSON.stringify(d, null, 2);
      loadPhone();
    });
    $$('[data-phone-cmd]').forEach((b) => b.addEventListener('click', async () => {
      const cmd = b.dataset.phoneCmd;
      b.disabled = true;
      const d = await api(`/api/phone/${cmd}`, { method: 'POST', timeout: 30000 });
      b.disabled = false;
      if (d && d.success) toast(`${cmd} sent — ${JSON.stringify(d).slice(0, 100)}`, 'success');
      else toast(`${cmd} failed — ${(d && d.error) || 'unknown'}`, 'error');
    }));
    $('#phone-contacts-btn').addEventListener('click', async () => {
      const q = $('#phone-contact-search').value.trim();
      const d = await api(`/api/phone/contacts/search?query=${encodeURIComponent(q)}`, { timeout: 30000 });
      const list = $('#phone-contacts');
      const contacts = (d && (d.contacts || d.results)) || [];
      list.innerHTML = contacts.length
        ? contacts.map((c) => `<div class="phone-row"><strong>${esc(c.name || 'unknown')}</strong> · ${esc(c.phone || c.number || '')}</div>`).join('')
        : `<div class="empty-state">${esc((d && d.error) || 'No contacts found (is the bridge connected?).')}</div>`;
    });
    $('#phone-msgs-refresh').addEventListener('click', async () => {
      const d = await api('/api/phone/messages', { timeout: 30000 });
      const list = $('#phone-messages');
      const msgs = (d && (d.messages || d.results)) || [];
      list.innerHTML = msgs.length
        ? msgs.map((m) => `<div class="phone-row"><strong>${esc(m.address || m.from || '?')}</strong><br>${esc(m.body || m.message || '')}</div>`).join('')
        : `<div class="empty-state">${esc((d && d.error) || 'No messages (is the bridge connected?).')}</div>`;
    });
  }

  /* ── Settings ─────────────────────────────────────────────────────── */
  const Settings = {
    integrations: {}, current: {},
  };
  async function loadSettingsView() {
    // Account pane — who is signed in + AI service status.
    renderAccountPane();
    api('/api/llm/status', { silent: true, timeout: 20000 }).then((s) => {
      const kv = $('#ai-kv');
      if (!kv) return;
      const state = s?.ai_service || 'unknown';
      kv.innerHTML = `<div class="kv"><span class="k">status</span><span class="v" style="color:${state === 'online' ? 'var(--ok)' : 'var(--warn)'}">${esc(state)}</span></div>
        <div class="kv"><span class="k">model</span><span class="v">${esc(s?.default_model || '(server default)')}</span></div>`;
    }).catch(() => { const kv = $('#ai-kv'); if (kv) kv.innerHTML = '<div class="empty-state">Status unavailable.</div>'; });
    try {
      const cur = await api('/api/iris/settings', { silent: true });
      Settings.current = cur || {};
      Settings.integrations = (cur && cur.integrations_schema) || {};
      renderIntegrations();
      const note = $('#storage-note');
      if (cur && cur.storage_warning) {
        note.hidden = false;
        note.textContent = cur.storage_warning;
      } else if (cur) {
        note.hidden = false;
        note.textContent = `Storage: ${cur.storage || 'unknown'} · ${cur.persistent ? 'persistent (database)' : 'temporary (not persisted across restarts)'}`;
      }
    } catch (e) {
      $('#integrations-grid').innerHTML = `<div class="empty-state">Settings unavailable — ${esc(e.message)}</div>`;
    }
  }
  function renderAccountPane() {
    const host = $('#account-info');
    if (!host) return;
    const u = Auth.user;
    if (!u) { host.innerHTML = '<div class="empty-state">Not signed in.</div>'; return; }
    const initials = (u.name || u.email || '?').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
    host.innerHTML = `
      <div class="account-row">
        ${u.picture ? `<img class="u-avatar lg" src="${esc(u.picture)}" alt="" referrerpolicy="no-referrer">` : `<span class="u-avatar lg u-initials">${esc(initials)}</span>`}
        <div class="u-info"><span class="u-name">${esc(u.name || 'Signed in')}</span>
        <span class="u-email">${esc(u.email || '')}</span></div>
      </div>
      <p class="muted" style="font-size:12.5px">Your chats, notes and settings are tied to this account and follow you on every device you sign in from.</p>
      <button class="btn btn-danger" id="account-signout">Sign out</button>`;
    $('#account-signout').addEventListener('click', () => Auth.signOut());
  }
  function initSettings() {
    $$('.settings-tab').forEach((tab) => tab.addEventListener('click', () => {
      $$('.settings-tab').forEach((c) => c.classList.toggle('active', c === tab));
      $$('.settings-pane').forEach((p) => { p.hidden = p.id !== `settings-${tab.dataset.settingsTab}`; });
      if (tab.dataset.settingsTab === 'system') loadSystemTab();
      if (tab.dataset.settingsTab === 'account') renderAccountPane();
    }));
    $('#integrations-save').addEventListener('click', async () => {
      const integrations = {};
      $$('#integrations-grid [data-ig]').forEach((el) => {
        const [name, field] = el.dataset.ig.split('.');
        integrations[name] = integrations[name] || {};
        if (el.value.trim()) integrations[name][field] = el.value.trim();
      });
      const d = await api('/api/iris/settings', { method: 'POST', body: { integrations } });
      if (d && d.success) toast('Integrations saved.', 'success');
      else toast((d && d.error) || 'save failed', 'error');
    });
    $('#system-refresh').addEventListener('click', loadSystemTab);
    $('#models-refresh').addEventListener('click', loadModelsTab);
    $('#self-analyze').addEventListener('click', async () => {
      const out = $('#system-output');
      out.hidden = false;
      out.textContent = 'Analyzing codebase…';
      const d = await api('/api/self/analyze', { timeout: 120000 });
      out.textContent = JSON.stringify(d, null, 2).slice(0, 4000);
    });
    $('#consciousness-reflect').addEventListener('click', async () => {
      const out = $('#system-output');
      out.hidden = false;
      out.textContent = 'Reflecting…';
      const d = await api('/api/consciousness/reflect', { timeout: 60000 });
      out.textContent = JSON.stringify(d, null, 2).slice(0, 4000);
    });
    $('#autonomous-queue').addEventListener('click', async () => {
      const task = $('#autonomous-task').value.trim();
      if (!task) { toast('Describe the task first.', 'warn'); return; }
      const d = await api('/api/autonomous/queue', { method: 'POST', timeout: 60000, body: { task } });
      if (d && d.success !== false) { toast('Task queued for the autonomous worker.', 'success'); $('#autonomous-task').value = ''; }
      else toast((d && d.error) || 'queue failed', 'error');
    });
    $('#tts-toggle').addEventListener('change', (e) => {
      try { localStorage.setItem('iris-tts', e.target.checked ? '1' : '0'); } catch { /* ignore */ }
      if (e.target.checked) Chat.speak('Text to speech enabled.');
    });
    try { $('#tts-toggle').checked = localStorage.getItem('iris-tts') === '1'; } catch { /* ignore */ }
  }
  function renderIntegrations() {
    const grid = $('#integrations-grid');
    grid.innerHTML = '';
    for (const [id, ig] of Object.entries(Settings.integrations || {})) {
      const saved = (Settings.current?.integrations?.[id]) || {};
      const card = document.createElement('div');
      card.className = 'integration-card';
      card.innerHTML = `
        <div class="ig-head"><h3>${esc(ig.label || id)}</h3>
          <span class="badge ${saved.configured ? 'ok' : ''}">${saved.configured ? 'configured' : 'optional'}</span></div>
        <p class="muted" style="font-size:12px;margin:0 0 10px">${esc(ig.description || '')}</p>
        ${(ig.fields || []).map((f) => `
          <label class="field" style="margin-bottom:8px"><span>${esc(f.label)}</span>
            <input class="input" data-ig="${esc(id)}.${esc(f.name)}" type="password" placeholder="${esc(f.placeholder || '')}">
          </label>`).join('')}`;
      grid.appendChild(card);
    }
  }
  async function loadSystemTab() {
    try {
      const [health, llm] = await Promise.all([
        api('/health', { silent: true }),
        api('/api/llm/status', { silent: true }),
      ]);
      const kv = $('#system-kv');
      kv.innerHTML = Object.entries({
        status: health?.status, version: health?.version,
        agents: health?.agents_registered, tools: health?.tools_available,
        modules: Object.values(health?.modules || {}).filter(Boolean).length + '/' + Object.keys(health?.modules || {}).length,
        timestamp: health?.timestamp && fmtTime(health.timestamp),
      }).map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v ?? '–'))}</span></div>`).join('');
      const lk = $('#llm-kv');
      lk.innerHTML = Object.entries({
        ai_service: llm?.ai_service || '–',
        model: llm?.default_model || '(server default)',
      }).map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v ?? '–'))}</span></div>`).join('');
      const auto = await api('/api/autonomous/status', { silent: true });
      $('#autonomous-badge').textContent = auto && auto.running ? 'running' : 'idle';
      $('#autonomous-badge').className = `badge ${auto && auto.running ? 'ok' : ''}`;
      const ak = $('#autonomous-kv');
      ak.innerHTML = Object.entries(auto || {}).slice(0, 8)
        .map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(v).slice(0, 80))}</span></div>`).join('');
    } catch (e) {
      $('#system-kv').innerHTML = `<div class="empty-state">System status unavailable — ${esc(e.message)}</div>`;
    }
  }
  async function loadModelsTab() {
    try {
      const d = await api('/api/scripts', { silent: true });
      const env = $('#models-env');
      const envInfo = d?.environment || {};
      env.textContent = Object.entries(envInfo).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'Environment info unavailable.';
      const grid = $('#models-grid');
      const models = (d?.models || d?.catalog || []);
      if (Array.isArray(models) && models.length) {
        grid.innerHTML = models.map((m) => `<div class="model-card"><div class="m-name">${esc(m.name || m.id || 'model')}</div><div class="m-meta">${esc([m.size, m.family, m.license].filter(Boolean).join(' · '))}</div></div>`).join('');
      } else {
        grid.innerHTML = '<div class="empty-state">No models listed — check the scripts API.</div>';
      }
      const jobs = d?.jobs || [];
      $('#jobs-count').textContent = String(jobs.length);
      const jl = $('#jobs-list');
      jl.innerHTML = jobs.length ? '' : '<div class="empty-state">No jobs yet.</div>';
      jobs.forEach((j) => {
        const el = document.createElement('div');
        el.className = 'job-item';
        el.innerHTML = `<span class="dot" data-state="${j.status === 'running' ? 'busy' : j.status === 'done' ? 'on' : 'off'}"></span>
          <strong>${esc(j.script || j.id || 'job')}</strong>
          <span class="badge ${j.status === 'running' ? 'accent' : ''}" style="margin-left:auto">${esc(j.status || 'unknown')}</span>`;
        el.addEventListener('click', async () => {
          const det = await api(`/api/scripts/jobs/${encodeURIComponent(j.id)}`, { silent: true });
          $('#job-console').hidden = false;
          $('#job-console-title').textContent = j.script || j.id;
          $('#job-console-out').textContent = (det && (det.output || det.stdout)) || JSON.stringify(det, null, 2);
        });
        jl.appendChild(el);
      });
    } catch (e) {
      $('#models-grid').innerHTML = `<div class="empty-state">Model registry unavailable — ${esc(e.message)}</div>`;
    }
  }
  function warnConsole(sel, msg) {
    const el = $(sel);
    if (el) el.innerHTML = `<div class="empty-state">${esc(msg)}</div>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     ROUTER
     ══════════════════════════════════════════════════════════════════════ */
  const ROUTES = {
    'chat':            { title: 'Chat',       sub: 'Autonomous multi-agent AI assistant', init: initChat, load: null },
    'agents':          { title: 'Agents',     sub: 'Delegate tasks — every agent runs for real', init: initAgents, load: loadAgentsView },
    'apps':            { title: 'Apps',       sub: 'Built-in tools, live APIs', init: null, load: loadAppsHub },
    'apps/calendar':   { title: 'Calendar',   sub: 'Schedule and events', init: initCalendarApp, load: loadCalendar },
    'apps/notes':      { title: 'Notes',      sub: 'Personal knowledge', init: initNotes, load: loadNotes },
    'apps/calculator': { title: 'Calculator', sub: 'Standard · scientific math · statistics', init: initCalculator, load: null },
    'apps/projects':   { title: 'Projects',   sub: 'Generate real scaffolds', init: initProjects, load: loadProjects },
    'apps/vision':     { title: 'Vision',     sub: 'Live screen & camera · real-time transcription', init: initVision, load: null },
    'apps/phone':      { title: 'Phone',      sub: 'ADB bridge · connect guide · command console', init: initPhone, load: loadPhone },
    'settings':        { title: 'Settings',   sub: 'Account · models & scripts · integrations · system', init: initSettings, load: loadSettingsView },
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

  /* ══════════════════════════════════════════════════════════════════════
     SIGN-IN GATE (Google Sign-In)
     The app stays locked behind the sign-in overlay until a valid session
     exists. Chat and personal data are tied to the signed-in account.
     ══════════════════════════════════════════════════════════════════════ */
  let authConfig = null;

  function waitForGoogle(timeout = 6000) {
    // The GIS script loads async/defer — poll until window.google appears.
    return new Promise((resolve) => {
      const t0 = Date.now();
      (function check() {
        if (window.google && window.google.accounts && window.google.accounts.id) return resolve(true);
        if (Date.now() - t0 > timeout) return resolve(false);
        setTimeout(check, 150);
      })();
    });
  }

  function showSignIn(expired) {
    const overlay = $('#signin-overlay');
    if (!overlay) return;
    overlay.hidden = false;
    document.documentElement.classList.add('modal-open');
    const status = $('#signin-status');
    if (authConfig && authConfig.sign_in_enabled) {
      status.textContent = expired ? 'Your session expired — sign in to continue.' : '';
      status.hidden = !expired;
      waitForGoogle().then((ok) => {
        if (!ok) {
          status.hidden = false;
          status.textContent = 'Could not load the Google sign-in button — check your connection and reload.';
          return;
        }
        try {
          window.google.accounts.id.initialize({
            client_id: authConfig.google_client_id,
            callback: onGoogleCredential,
          });
          window.google.accounts.id.renderButton($('#gsi-button'), {
            theme: 'outline', size: 'large', width: 320, text: 'continue_with',
          });
        } catch (e) {
          status.hidden = false;
          status.textContent = `Sign-in button failed: ${e.message}`;
        }
      });
    } else {
      status.hidden = false;
      status.textContent = (authConfig && authConfig.reason)
        || 'Sign-in is not configured on the server yet. Please contact your administrator.';
    }
  }

  function hideSignIn() {
    const overlay = $('#signin-overlay');
    if (overlay) overlay.hidden = true;
    document.documentElement.classList.remove('modal-open');
  }

  async function onGoogleCredential(resp) {
    const status = $('#signin-status');
    status.hidden = false;
    status.textContent = 'Signing you in…';
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: resp.credential }),
      });
      const d = await res.json().catch(() => null);
      if (res.ok && d && d.success && d.token) {
        Auth.save(d.token);
        Auth.user = d.user;
        hideSignIn();
        startApp();
        toast(`Welcome, ${d.user && d.user.name ? d.user.name.split(' ')[0] : 'back'}!`, 'success', 'IRIS');
      } else {
        status.textContent = (d && d.error) || 'Sign-in failed. Please try again.';
      }
    } catch (e) {
      status.textContent = `Sign-in failed: ${e.message}`;
    }
  }

  function startApp() {
    // First visit lands on chat; a returning hash route is preserved.
    render();
    scheduleHealth();
    renderUserChip();
  }

  /* ── Boot ─────────────────────────────────────────────────────────── */
  (async function boot() {
    initSidebar();
    try {
      authConfig = await api('/api/auth/config', { silent: true, timeout: 15000 });
    } catch { authConfig = null; }
    if (!authConfig || !authConfig.sign_in_enabled) {
      authConfig = authConfig || { sign_in_enabled: false };
      showSignIn();
      return;
    }
    const ok = await Auth.restore();
    if (!ok) { showSignIn(); return; }
    hideSignIn();
    startApp();
  })();

  window.IRIS = { Chat, Terminals, Agents, Theme, Auth, toast, navigate };
})();
