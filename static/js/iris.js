/* IRIS v8 Dashboard — wired to live backend APIs only.
 * No simulated or hardcoded data. Every panel reflects real server state.
 *
 * Endpoints used (all real, provided by app.py + api/routes blueprints):
 *   /api/status                    system_bp   (uptime, emotion, awareness, autonomous)
 *   /api/chat                      chat_bp     (LLM orchestrator)
 *   /api/omnis/agents              app.py      (agent registry + specialties)
 *   /api/omnis/status              app.py      (execution log, health, cron)
 *   /api/omnis/delegate            app.py      (real agent task delegation)
 *   /api/calendar/today|events     calendar_bp (persistent calendar skill)
 *   /api/notes                     notes_bp    (persistent notes skill)
 *   /api/math/*                    math_bp     (real math engine)
 *   /api/projects|generate         projects_bp (project generator)
 *   /api/phone/*                   phone_bp    (ADB phone bridge)
 *   /api/vision/stream/*|frame     vision_bp   (vision module)
 *   /api/voice/*                   voice_bp    (voice system)
 *   /api/self/analyze              self_improve_bp
 *   /api/consciousness/reflect     consciousness_bp
 */
'use strict';

class IRISApp {
    constructor() {
        this.sessionId = localStorage.getItem('iris_session') || null;
        this.currentSection = 'chat';
        this.isStreaming = false;
        this.visionTimer = null;
        this.statusTimer = null;
        this.activityTimer = null;
        this.agents = [];
        this.agentTasks = new Map();   // agentName -> [{task, result, at}]
        this.openTabs = new Map();     // tabId -> {agent, el}
        this.tabSeq = 0;
        this.init();
    }

    init() {
        this.setupNavigation();
        this.setupChat();
        this.setupVoice();
        this.setupVision();
        this.setupPhone();
        this.setupCalendar();
        this.setupNotes();
        this.setupMath();
        this.setupProjects();
        this.setupSettings();
        this.setupAgents();
        this.setupModal();
        this.refreshStatus();
        this.startStatusPolling();
    }

    /* ─────────────────────────── shared helpers ─────────────────────────── */

    static esc(value) {
        if (value === null || value === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(value);
        return div.innerHTML;
    }

    static timeAgo(iso) {
        if (!iso) return '';
        const then = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').getTime();
        if (isNaN(then)) return '';
        const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
        if (s < 60) return `${s}s ago`;
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        return `${Math.floor(s / 3600)}h ago`;
    }

    async safeFetch(url, options = {}) {
        let res;
        try {
            res = await fetch(url, options);
        } catch (e) {
            throw new Error('Network unreachable');
        }
        let data = null;
        try {
            data = await res.json();
        } catch (e) {
            /* non-JSON body (HTML error page etc.) */
        }
        if (!res.ok) {
            const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
            const err = new Error(msg);
            err.status = res.status;
            throw err;
        }
        if (data === null) throw new Error('Invalid server response');
        return data;
    }

    toast(message, kind = 'info') {
        const stack = document.getElementById('toast-stack');
        const el = document.createElement('div');
        el.className = `toast toast-${kind}`;
        el.textContent = message;
        stack.appendChild(el);
        requestAnimationFrame(() => el.classList.add('show'));
        setTimeout(() => {
            el.classList.remove('show');
            setTimeout(() => el.remove(), 400);
        }, kind === 'error' ? 6000 : 3500);
    }

    setEmptyState(el, text) {
        el.innerHTML = `<div class="empty-state">${IRISApp.esc(text)}</div>`;
    }

    /* ─────────────────────────── navigation ─────────────────────────── */

    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.dataset.section;
                if (!section) return;
                this.switchSection(section);
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }

    switchSection(section) {
        const target = document.getElementById(`${section}-section`);
        if (!target) return;
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        target.classList.add('active');
        this.currentSection = section;

        const titles = {
            chat: 'Chat with IRIS',
            agents: 'Agent Workspace',
            calendar: 'Aevibron Calendar',
            notes: 'Aevibron Notes',
            projects: 'Project Generator',
            phone: 'Phone Control',
            vision: 'Vision Stream',
            math: 'Aevibron Math',
            settings: 'Settings'
        };
        document.getElementById('page-title').textContent = titles[section] || 'IRIS';

        if (section === 'calendar') this.loadCalendar();
        if (section === 'notes') this.loadNotes();
        if (section === 'projects') this.loadProjects();
        if (section === 'phone') this.loadPhoneData();
        if (section === 'settings') this.loadSettings();
        if (section === 'agents') { this.loadAgents(); this.loadActivity(); }
    }

    /* ─────────────────────────── chat ─────────────────────────── */

    setupChat() {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        sendBtn.addEventListener('click', () => this.sendMessage());

        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        });
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';
        input.style.height = 'auto';
        this.addMessage('user', message);
        this.showTyping();

        try {
            const data = await this.safeFetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: this.sessionId })
            });
            this.hideTyping();
            if (data.success) {
                this.sessionId = data.session_id;
                localStorage.setItem('iris_session', this.sessionId);
                this.addMessage('assistant', data.response);
                if (data.emotion) this.updateEmotion(data.emotion);
                if (data.proactive_suggestion) {
                    this.addMessage('assistant', `💡 ${data.proactive_suggestion}`);
                }
            } else {
                this.addMessage('assistant', `Error: ${data.error || 'request failed'}`);
            }
        } catch (e) {
            this.hideTyping();
            this.addMessage('assistant', `Connection error: ${e.message}`);
        }
    }

    addMessage(role, content) {
        const messages = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = `message ${role}`;
        const avatar = role === 'assistant' ? 'I' : 'U';
        div.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <p>${IRISApp.esc(content).replace(/\n/g, '<br>')}</p>
                <span class="message-time">${new Date().toLocaleTimeString()}</span>
            </div>`;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    showTyping() {
        const messages = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = 'message assistant typing-indicator';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="message-avatar">I</div>
            <div class="message-content"><p>Thinking<span class="dots">...</span></p></div>`;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    hideTyping() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    /* ─────────────────────────── agents workspace ───────────────────────────
     * Real data sources:
     *   roster      -> GET /api/omnis/agents   {agents:[{name,specialties}], count}
     *   activity    -> GET /api/omnis/status   {execution_log, health, cron_jobs}
     *   delegation  -> POST /api/omnis/delegate {agent, task} -> real agent result
     */
    setupAgents() {
        document.getElementById('agent-search').addEventListener('input', (e) => {
            this.renderAgentRoster(e.target.value.trim().toLowerCase());
        });
        document.getElementById('activity-refresh').addEventListener('click', () => this.loadActivity());
    }

    async loadAgents() {
        const grid = document.getElementById('agent-grid');
        try {
            const data = await this.safeFetch('/api/omnis/agents');
            this.agents = (data.agents || []).map(a =>
                typeof a === 'string' ? { name: a, specialties: [] } : a
            );
            this.renderAgentRoster(document.getElementById('agent-search').value.trim().toLowerCase());
            this.renderAgentStats();
        } catch (e) {
            this.setEmptyState(grid, `Could not load agent registry: ${e.message}`);
        }
    }

    renderAgentStats() {
        const el = document.getElementById('agents-stats');
        if (!el) return;
        const working = this.agentTasks.size;
        el.innerHTML = `
            <span class="stat-chip">${this.agents.length} agents</span>
            <span class="stat-chip ${working ? 'chip-accent' : ''}">${working} working</span>
            <span class="stat-chip">${[...this.agentTasks.values()].reduce((n, h) => n + h.length, 0)} tasks run</span>`;
        const badge = document.getElementById('agents-badge');
        if (badge) {
            badge.textContent = String(working);
            badge.classList.toggle('active', working > 0);
        }
    }

    renderAgentRoster(filter) {
        const grid = document.getElementById('agent-grid');
        if (!this.agents.length) {
            this.setEmptyState(grid, 'No agents returned by the registry.');
            return;
        }
        const list = filter
            ? this.agents.filter(a =>
                a.name.toLowerCase().includes(filter) ||
                (a.specialties || []).some(s => s.toLowerCase().includes(filter)))
            : this.agents;

        if (!list.length) {
            this.setEmptyState(grid, `No agents match "${filter}".`);
            return;
        }
        grid.innerHTML = list.map(a => {
            const working = this.agentTasks.has(a.name);
            const canDelegate = a.delegatable !== false;
            return `
            <div class="agent-card ${working ? 'agent-working' : ''}">
                <div class="agent-name">${IRISApp.esc(a.name)}</div>
                <div class="agent-specs">${(a.specialties || []).map(s => IRISApp.esc(s)).join(' · ') || 'generalist'}</div>
                <div class="agent-card-footer">
                    <span class="agent-state" title="${canDelegate ? 'Supports real task delegation via /api/omnis/delegate' : 'Loaded, but exposes no delegation interface'}">${working ? '● working' : canDelegate ? '○ delegatable' : '○ manual'}</span>
                    <button class="btn-primary btn-sm" data-agent="${IRISApp.esc(a.name)}">Open</button>
                </div>
            </div>`;
        }).join('');

        grid.querySelectorAll('button[data-agent]').forEach(btn => {
            btn.addEventListener('click', () => this.openAgentTab(btn.dataset.agent));
        });
    }

    openAgentTab(agentName) {
        const agent = this.agents.find(a => a.name === agentName) || { name: agentName, specialties: [] };
        const tabId = `tab-${agentName}`;
        if (this.openTabs.has(tabId)) {
            this.activateTab(tabId);
            return;
        }

        if (!this.agentTasks.has(agentName)) this.agentTasks.set(agentName, []);

        const bar = document.getElementById('agent-tab-bar');
        document.getElementById('tab-empty')?.remove();

        const tab = document.createElement('button');
        tab.className = 'tab';
        tab.id = tabId;
        tab.innerHTML = `
            <span class="tab-label">${IRISApp.esc(agentName)}</span>
            <span class="tab-close" title="Close">&times;</span>`;
        bar.appendChild(tab);

        const panel = document.createElement('div');
        panel.className = 'tab-panel';
        panel.dataset.tab = tabId;
        panel.innerHTML = `
            <div class="panel-head">
                <div>
                    <div class="panel-agent">${IRISApp.esc(agentName)}</div>
                    <div class="panel-specs">${(agent.specialties || []).map(s => IRISApp.esc(s)).join(' · ') || 'generalist'}</div>
                </div>
                <span class="panel-status" data-role="status">idle</span>
            </div>
            <div class="panel-task">
                <textarea data-role="task-input" rows="3" placeholder="Describe a task for ${IRISApp.esc(agentName)} to execute for real (sent via /api/omnis/delegate)…"></textarea>
                <div class="panel-task-actions">
                    <button class="btn-primary btn-sm" data-role="run-btn">Run Task</button>
                </div>
            </div>
            <div class="panel-history" data-role="history">
                <div class="empty-state">No tasks yet for this agent.</div>
            </div>`;
        document.getElementById('agent-tab-panels').appendChild(panel);

        tab.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-close')) {
                this.closeTab(tabId);
            } else {
                this.activateTab(tabId);
            }
        });

        panel.querySelector('[data-role="run-btn"]').addEventListener('click', async () => {
            const ta = panel.querySelector('[data-role="task-input"]');
            const text = ta.value.trim();
            if (!text) { this.toast('Describe the task first.', 'error'); return; }
            const meta = this.agents.find(x => x.name === agentName);
            if (meta && meta.delegatable === false) {
                this.toast(`${agentName} exposes no delegation interface — the attempt will run and may return an honest error.`, 'info');
            }
            await this.delegateTask(agentName, text, panel);
            ta.value = '';
        });

        this.openTabs.set(tabId, { agent: agentName, panel });
        this.activateTab(tabId);
        this.renderAgentRoster(document.getElementById('agent-search').value.trim().toLowerCase());
        this.renderAgentStats();
    }

    activateTab(tabId) {
        document.querySelectorAll('#agent-tab-bar .tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('#agent-tab-panels .tab-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(tabId)?.classList.add('active');
        document.querySelector(`.tab-panel[data-tab="${tabId}"]`)?.classList.add('active');
    }

    closeTab(tabId) {
        document.getElementById(tabId)?.remove();
        document.querySelector(`.tab-panel[data-tab="${tabId}"]`)?.remove();
        this.openTabs.delete(tabId);
        const remaining = [...this.openTabs.keys()];
        if (!remaining.length) {
            const bar = document.getElementById('agent-tab-bar');
            bar.innerHTML = '<div class="tab-empty" id="tab-empty">No agents working yet. Pick an agent from the roster and delegate a task.</div>';
        } else {
            this.activateTab(remaining[remaining.length - 1]);
        }
        this.renderAgentStats();
    }

    async delegateTask(agentName, taskText, panel) {
        const status = panel.querySelector('[data-role="status"]');
        const history = panel.querySelector('[data-role="history"]');
        status.textContent = 'working';
        status.className = 'panel-status working';

        const entry = { task: taskText, result: null, at: new Date().toISOString(), ok: null };
        const record = this.agentTasks.get(agentName) || [];
        record.push(entry);
        this.agentTasks.set(agentName, record);
        this.renderPanelHistory(agentName, history);
        this.renderAgentStats();

        try {
            const data = await this.safeFetch('/api/omnis/delegate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent: agentName,
                    task: { type: 'request', description: taskText, request: taskText }
                })
            });
            entry.ok = !!data.success;
            entry.result = data.success
                ? data.result
                : { error: data.error || 'delegation failed' };
            status.textContent = data.success ? 'completed' : 'error';
            status.className = `panel-status ${data.success ? 'done' : 'errored'}`;
            this.toast(data.success
                ? `${agentName} finished the task.`
                : `${agentName} failed: ${data.error}`, data.success ? 'success' : 'error');
        } catch (e) {
            entry.ok = false;
            entry.result = { error: e.message };
            status.textContent = 'error';
            status.className = 'panel-status errored';
            this.toast(`Delegation error: ${e.message}`, 'error');
        }
        this.renderPanelHistory(agentName, history);
        this.renderAgentStats();
        this.loadActivity();
    }

    renderPanelHistory(agentName, historyEl) {
        const record = this.agentTasks.get(agentName) || [];
        if (!record.length) {
            this.setEmptyState(historyEl, 'No tasks yet for this agent.');
            return;
        }
        historyEl.innerHTML = record.slice().reverse().map(e => `
            <div class="history-entry ${e.ok === true ? 'ok' : e.ok === false ? 'bad' : 'pending'}">
                <div class="history-task">${IRISApp.esc(e.task)}</div>
                <div class="history-time">${IRISApp.esc(e.at.replace('T', ' ').slice(0, 19))} · ${e.ok === null ? 'running' : e.ok ? 'success' : 'failed'}</div>
                <pre class="history-result">${IRISApp.esc(JSON.stringify(e.result ?? { status: 'pending' }, null, 2))}</pre>
            </div>`).join('');
    }

    async loadActivity() {
        const log = document.getElementById('activity-log');
        const meta = document.getElementById('activity-meta');
        try {
            const data = await this.safeFetch('/api/omnis/status');
            const entries = data.execution_log || [];
            meta.innerHTML = `
                <span class="stat-chip ${data.running ? 'chip-accent' : ''}">${data.running ? 'OMNIS running' : 'OMNIS stopped'}</span>
                <span class="stat-chip">${(data.available_agents || []).length} agents</span>
                <span class="stat-chip">${data.cron_jobs ?? 0} cron jobs</span>
                <span class="stat-chip">session ${IRISApp.esc((data.session_id || '').slice(0, 8))}</span>`;

            if (!entries.length) {
                this.setEmptyState(log, 'No executions yet. Delegate a task to an agent to begin.');
                return;
            }
            log.innerHTML = entries.slice().reverse().map(e => `
                <div class="log-entry ${e.status === 'success' ? 'ok' : 'bad'}">
                    <span class="log-status">${e.status === 'success' ? '✔' : '✘'}</span>
                    <span class="log-skill">${IRISApp.esc(e.skill || e.capability)}</span>
                    <span class="log-cap">${IRISApp.esc(e.capability)}</span>
                    <span class="log-time">${IRISApp.timeAgo(e.completed_at || e.started_at)}</span>
                </div>`).join('');
        } catch (e) {
            meta.textContent = 'OMNIS status unavailable.';
            this.setEmptyState(log, `Activity feed error: ${e.message}`);
        }
    }

    /* ─────────────────────────── voice ─────────────────────────── */

    setupVoice() {
        document.getElementById('voice-btn').addEventListener('click', () => {
            document.getElementById('voice-overlay').classList.add('active');
            this.startVoiceListening();
        });
        document.getElementById('voice-close-btn').addEventListener('click', () => {
            document.getElementById('voice-overlay').classList.remove('active');
        });
    }

    async startVoiceListening() {
        const text = document.getElementById('voice-text');
        text.textContent = 'Listening…';
        try {
            const data = await this.safeFetch('/api/voice/listen', { method: 'POST' });
            if (data.success) {
                text.textContent = `You said: "${data.text}"`;
                document.getElementById('chat-input').value = data.text;
                await this.sendMessage();
                setTimeout(() => {
                    document.getElementById('voice-overlay').classList.remove('active');
                }, 2000);
            } else {
                text.textContent = data.error || 'Voice recognition unavailable';
            }
        } catch (e) {
            text.textContent = `Voice recognition not available (${e.message})`;
        }
    }

    /* ─────────────────────────── vision ─────────────────────────── */

    setupVision() {
        document.getElementById('start-vision-btn').addEventListener('click', async () => {
            try {
                const data = await this.safeFetch('/api/vision/stream/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source: 'screen', interval: 2.0 })
                });
                this.toast(data.message || 'Vision stream started', 'success');
                this.startVisionFeed();
            } catch (e) {
                this.toast(`Could not start stream: ${e.message}`, 'error');
            }
        });

        document.getElementById('stop-vision-btn').addEventListener('click', async () => {
            try {
                await this.safeFetch('/api/vision/stream/stop', { method: 'POST' });
                this.stopVisionFeed();
                this.toast('Vision stream stopped', 'info');
            } catch (e) {
                this.toast(`Stop failed: ${e.message}`, 'error');
            }
        });

        document.getElementById('analyze-vision-btn').addEventListener('click', async () => {
            const out = document.getElementById('vision-analysis');
            out.innerHTML = '<span class="text-muted">Analyzing current view…</span>';
            try {
                const data = await this.safeFetch('/api/vision/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: 'What do you see?' })
                });
                out.textContent = data.success ? data.analysis : `Error: ${data.error}`;
            } catch (e) {
                out.textContent = `Error: ${e.message}`;
            }
        });
    }

    startVisionFeed() {
        this.stopVisionFeed();
        const feed = document.getElementById('vision-feed');
        feed.innerHTML = '<img id="vision-frame" alt="Live vision frame">';
        this.isStreaming = true;

        const poll = async () => {
            if (!this.isStreaming) return;
            try {
                const data = await this.safeFetch('/api/vision/frame');
                const img = document.getElementById('vision-frame');
                if (img && data.success && data.frame) {
                    img.src = `data:image/jpeg;base64,${data.frame}`;
                }
            } catch (e) { /* transient poll failure — keep polling */ }
            if (this.isStreaming) this.visionTimer = setTimeout(poll, 2000);
        };
        poll();
    }

    stopVisionFeed() {
        this.isStreaming = false;
        if (this.visionTimer) { clearTimeout(this.visionTimer); this.visionTimer = null; }
    }

    /* ─────────────────────────── phone ─────────────────────────── */

    setupPhone() {
        document.getElementById('torch-btn').addEventListener('click', () => this.phoneAction('torch', { state: 'toggle' }, 'Torch'));
        document.getElementById('wifi-btn').addEventListener('click', () => this.phoneAction('wifi', { state: 'toggle' }, 'WiFi'));
        document.getElementById('bluetooth-btn').addEventListener('click', () => this.phoneAction('bluetooth', { state: 'toggle' }, 'Bluetooth'));
        document.getElementById('camera-btn-phone').addEventListener('click', () => this.phoneAction('camera', { action: 'open' }, 'Camera'));
        document.getElementById('contact-search').addEventListener('input', async (e) => {
            const q = e.target.value.trim();
            if (!q) { this.renderContacts(null); return; }
            try {
                const data = await this.safeFetch(`/api/phone/contacts/search?q=${encodeURIComponent(q)}`);
                this.renderContacts(data);
            } catch (err) { /* keep current list */ }
        });
    }

    async phoneAction(endpoint, body, label) {
        try {
            const data = await this.safeFetch(`/api/phone/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            this.toast(data.success
                ? `${label}: done`
                : `${label}: ${data.error || (data.stdout || 'device not reachable')}`, data.success ? 'success' : 'error');
            this.loadPhoneData();
        } catch (e) {
            this.toast(`${label}: ${e.message}`, 'error');
        }
    }

    async loadPhoneData() {
        try {
            const status = await this.safeFetch('/api/status');
            const bridge = status.phone_bridge || {};
            const state = document.getElementById('phone-bridge-state');
            state.textContent = bridge.available ? 'ADB bridge connected' : 'ADB bridge not connected — actions will report device errors';
            state.className = bridge.available ? 'workspace-hint ok' : 'workspace-hint';
        } catch (e) { /* status optional here */ }

        try {
            const battery = await this.safeFetch('/api/phone/battery');
            const el = document.getElementById('battery-info');
            el.textContent = battery.success && battery.level !== null
                ? `${battery.level}% — ${battery.status || 'unknown status'}`
                : (battery.error || 'Not connected');
        } catch (e) {
            document.getElementById('battery-info').textContent = `Battery info unavailable (${e.message})`;
        }

        try {
            const contacts = await this.safeFetch('/api/phone/contacts');
            this.renderContacts(contacts);
        } catch (e) {
            document.getElementById('contacts-list').innerHTML =
                `<div class="empty-state">Contacts unavailable: ${IRISApp.esc(e.message)}</div>`;
        }

        try {
            const messages = await this.safeFetch('/api/phone/messages?limit=5');
            const list = document.getElementById('phone-messages-list');
            if (messages.success && (messages.messages || []).length) {
                list.innerHTML = messages.messages.slice(0, 5).map(m => `
                    <div class="message-item">
                        <strong>${IRISApp.esc(m.address || 'unknown')}</strong>
                        <span>${IRISApp.esc((m.body || '').substring(0, 60))}</span>
                    </div>`).join('');
            } else {
                this.setEmptyState(list, messages.error || 'No messages (device not connected).');
            }
        } catch (e) {
            document.getElementById('phone-messages-list').innerHTML =
                `<div class="empty-state">Messages unavailable: ${IRISApp.esc(e.message)}</div>`;
        }
    }

    renderContacts(data) {
        const list = document.getElementById('contacts-list');
        if (!data) {
            this.setEmptyState(list, 'No contacts loaded.');
            return;
        }
        if (data.success && (data.contacts || []).length) {
            list.innerHTML = data.contacts.slice(0, 20).map(c => `
                <div class="contact-item">
                    <strong>${IRISApp.esc(c.name)}</strong>
                    <span>${IRISApp.esc(c.number)}</span>
                </div>`).join('');
        } else {
            this.setEmptyState(list, data.error || 'No contacts (device not connected).');
        }
    }

    /* ─────────────────────────── calendar ─────────────────────────── */

    setupCalendar() {
        document.getElementById('calendar-refresh').addEventListener('click', () => this.loadCalendar());
        document.getElementById('add-event-btn').addEventListener('click', () => this.showEventForm());
    }

    async loadCalendar() {
        const el = document.getElementById('events-list');
        try {
            const data = await this.safeFetch('/api/calendar/today');
            if (data.success && (data.events || []).length) {
                el.innerHTML = data.events.map(e => `
                    <div class="event-item">
                        <div class="event-title">${IRISApp.esc(e.title)}</div>
                        <div class="event-time">${IRISApp.esc(e.start_time || '')}${e.end_time ? ' → ' + IRISApp.esc(e.end_time) : ''}</div>
                        ${e.description ? `<p>${IRISApp.esc(e.description)}</p>` : ''}
                        <span class="event-cat">${IRISApp.esc(e.category || 'general')}</span>
                    </div>`).join('');
            } else {
                this.setEmptyState(el, `No events today (${IRISApp.esc(data.date || '')}).`);
            }
        } catch (e) {
            this.setEmptyState(el, `Calendar unavailable: ${e.message}`);
        }
    }

    showEventForm() {
        this.openModal('Add Calendar Event', `
            <div class="form-grid">
                <label>Title<input id="ev-title" placeholder="Standup with IRIS team"></label>
                <label>Start (YYYY-MM-DD HH:MM)<input id="ev-start" placeholder="2026-10-25 09:00"></label>
                <label>End (optional)<input id="ev-end" placeholder="2026-10-25 10:00"></label>
                <label>Description<textarea id="ev-desc" rows="2"></textarea></label>
            </div>
            <div class="modal-actions">
                <button class="btn-secondary" id="ev-cancel">Cancel</button>
                <button class="btn-primary" id="ev-save">Save Event</button>
            </div>`);

        document.getElementById('ev-cancel').addEventListener('click', () => this.closeModal());
        document.getElementById('ev-save').addEventListener('click', async () => {
            const title = document.getElementById('ev-title').value.trim();
            const start = document.getElementById('ev-start').value.trim();
            if (!title || !start) { this.toast('Title and start time are required.', 'error'); return; }
            try {
                const data = await this.safeFetch('/api/calendar/events', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title,
                        start_time: start,
                        end_time: document.getElementById('ev-end').value.trim() || null,
                        description: document.getElementById('ev-desc').value.trim()
                    })
                });
                if (data.success) {
                    this.toast('Event saved', 'success');
                    this.closeModal();
                    this.loadCalendar();
                } else {
                    this.toast(data.error || 'Save failed', 'error');
                }
            } catch (e) {
                this.toast(`Save failed: ${e.message}`, 'error');
            }
        });
    }

    /* ─────────────────────────── notes ─────────────────────────── */

    setupNotes() {
        document.getElementById('notes-refresh').addEventListener('click', () => this.loadNotes());
        document.getElementById('add-note-btn').addEventListener('click', () => this.showNoteForm());
    }

    async loadNotes() {
        const grid = document.getElementById('notes-grid');
        try {
            const data = await this.safeFetch('/api/notes');
            if (data.success && (data.notes || []).length) {
                grid.innerHTML = data.notes.map(n => `
                    <div class="note-card">
                        <h4>${IRISApp.esc(n.title)}</h4>
                        <p>${IRISApp.esc((n.content || '').substring(0, 140))}</p>
                        <small>${IRISApp.esc(n.category || 'general')}</small>
                    </div>`).join('');
            } else {
                this.setEmptyState(grid, 'No notes yet. Create one to get started.');
            }
        } catch (e) {
            this.setEmptyState(grid, `Notes unavailable: ${e.message}`);
        }
    }

    showNoteForm() {
        this.openModal('New Note', `
            <div class="form-grid">
                <label>Title<input id="note-title" placeholder="Ideas for IRIS v9"></label>
                <label>Content<textarea id="note-content" rows="4"></textarea></label>
                <label>Category<input id="note-category" placeholder="general"></label>
            </div>
            <div class="modal-actions">
                <button class="btn-secondary" id="note-cancel">Cancel</button>
                <button class="btn-primary" id="note-save">Save Note</button>
            </div>`);

        document.getElementById('note-cancel').addEventListener('click', () => this.closeModal());
        document.getElementById('note-save').addEventListener('click', async () => {
            const title = document.getElementById('note-title').value.trim();
            if (!title) { this.toast('Title is required.', 'error'); return; }
            try {
                const data = await this.safeFetch('/api/notes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title,
                        content: document.getElementById('note-content').value.trim(),
                        category: document.getElementById('note-category').value.trim() || 'general'
                    })
                });
                if (data.success) {
                    this.toast('Note saved', 'success');
                    this.closeModal();
                    this.loadNotes();
                } else {
                    this.toast(data.error || 'Save failed', 'error');
                }
            } catch (e) {
                this.toast(`Save failed: ${e.message}`, 'error');
            }
        });
    }

    /* ─────────────────────────── math ─────────────────────────── */

    setupMath() {
        document.querySelectorAll('.math-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.doMath(btn.dataset.op, document.getElementById('math-expression').value);
            });
        });
    }

    async doMath(operation, expression) {
        const resultDiv = document.getElementById('math-result');
        if (!expression.trim()) {
            resultDiv.innerHTML = '<span class="text-muted">Enter an expression first.</span>';
            return;
        }
        const endpoints = {
            solve: '/api/math/solve',
            simplify: '/api/math/simplify',
            differentiate: '/api/math/differentiate',
            integrate: '/api/math/integrate',
            evaluate: '/api/math/evaluate'
        };
        resultDiv.innerHTML = '<span class="text-muted">Computing…</span>';
        try {
            const data = await this.safeFetch(endpoints[operation], {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expression })
            });
            resultDiv.innerHTML = data.success
                ? `<pre>${IRISApp.esc(JSON.stringify(data.result ?? data, null, 2))}</pre>`
                : `<span class="math-error">Error: ${IRISApp.esc(data.error)}</span>`;
        } catch (e) {
            resultDiv.innerHTML = `<span class="math-error">Error: ${IRISApp.esc(e.message)}</span>`;
        }
    }

    /* ─────────────────────────── projects ─────────────────────────── */

    setupProjects() {
        document.getElementById('projects-refresh').addEventListener('click', () => this.loadProjects());
        document.getElementById('generate-project-btn').addEventListener('click', async () => {
            const name = document.getElementById('project-name').value.trim();
            const template = document.getElementById('project-template').value;
            const description = document.getElementById('project-desc').value.trim();
            if (!name) { this.toast('Project name required.', 'error'); return; }
            try {
                const data = await this.safeFetch('/api/projects/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, template, description })
                });
                if (data.success) {
                    this.toast(`Project "${name}" generated at ${data.path || 'workspace'}`, 'success');
                    this.loadProjects();
                } else {
                    this.toast(data.error || 'Generation failed', 'error');
                }
            } catch (e) {
                this.toast(`Generation failed: ${e.message}`, 'error');
            }
        });
    }

    async loadProjects() {
        const el = document.getElementById('projects-list');
        try {
            const data = await this.safeFetch('/api/projects');
            if (data.success && (data.projects || []).length) {
                el.innerHTML = data.projects.map(p => `
                    <div class="project-card">
                        <h4>${IRISApp.esc(p.name)}</h4>
                        <p class="mono">${IRISApp.esc(p.path || '')}</p>
                        <small>${IRISApp.esc(p.created || '')}</small>
                    </div>`).join('');
            } else {
                this.setEmptyState(el, 'No projects yet. Generate one above.');
            }
        } catch (e) {
            this.setEmptyState(el, `Projects unavailable: ${e.message}`);
        }
    }

    /* ─────────────────────────── settings ─────────────────────────── */

    setupSettings() {
        document.getElementById('analyze-self-btn').addEventListener('click', async () => {
            const out = document.getElementById('self-analysis-result');
            out.innerHTML = '<span class="text-muted">Analyzing codebase…</span>';
            try {
                const data = await this.safeFetch('/api/self/analyze');
                out.innerHTML = `<pre>${IRISApp.esc(JSON.stringify(data, null, 2))}</pre>`;
            } catch (e) {
                out.textContent = `Error: ${e.message}`;
            }
        });

        document.getElementById('reflect-btn').addEventListener('click', async () => {
            const out = document.getElementById('reflection-result');
            out.innerHTML = '<span class="text-muted">Reflecting…</span>';
            try {
                const data = await this.safeFetch('/api/consciousness/reflect');
                out.textContent = data.reflection || data.error || JSON.stringify(data, null, 2);
            } catch (e) {
                out.textContent = `Error: ${e.message}`;
            }
        });
    }

    async loadSettings() {
        try {
            const status = await this.safeFetch('/api/status');
            document.getElementById('setting-uptime').textContent = status.iris?.uptime ?? '--';
            document.getElementById('setting-emotion').textContent = status.iris?.emotion?.dominant ?? '--';
            document.getElementById('setting-awareness').textContent =
                status.iris?.awareness !== undefined ? `${(status.iris.awareness * 100).toFixed(1)}%` : '--';
            document.getElementById('setting-db').textContent = status.database || '--';
            document.getElementById('autonomous-status').textContent =
                status.autonomous?.running ? 'Running' : 'Stopped';
            document.getElementById('queue-size').textContent = status.autonomous?.queue_size ?? '--';
            document.getElementById('scheduled-tasks').textContent =
                status.autonomous?.scheduled_tasks ?? '--';
        } catch (e) {
            this.toast(`Settings load failed: ${e.message}`, 'error');
        }
    }

    /* ─────────────────────────── status & polling ─────────────────────────── */

    async refreshStatus() {
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        try {
            const data = await this.safeFetch('/api/status');
            dot.className = 'status-dot online';
            text.textContent = 'IRIS Online';
            this.updateEmotion(data.iris?.emotion?.dominant);
        } catch (e) {
            dot.className = 'status-dot offline';
            text.textContent = 'IRIS Offline';
            this.updateEmotion(null);
        }
    }

    startStatusPolling() {
        this.statusTimer = setInterval(() => this.refreshStatus(), 30000);
        /* Agent activity feed refresh whenever the agents tab is open */
        this.activityTimer = setInterval(() => {
            if (this.currentSection === 'agents') this.loadActivity();
        }, 10000);
    }

    updateEmotion(emotion) {
        document.getElementById('emotion-display').textContent = emotion ? `feeling: ${emotion}` : 'feeling: —';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.irisApp = new IRISApp();
});
