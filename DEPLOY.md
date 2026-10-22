# IRIS — Architecture & Deployment Guide

> **IRIS v2** — autonomous AI agent system with 30 agents, 100 capabilities,
> multi-LLM provider routing (Aevibron/Ollama/Groq/OpenAI), self-healing
> autonomous loop, Hermes-style device control, GitHub integration, inbuilt
> apps (calendar/calculator/maps/file explorer).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Deploy on Vercel](#deploy-on-vercel)
3. [Deploy with Docker](#deploy-with-docker)
4. [Deploy on a VPS](#deploy-on-a-vps)
5. [Multi-LLM Provider Setup](#multi-llm-provider-setup)
6. [Wake Word + Always-On Architecture](#wake-word--always-on-architecture)
7. [APK via GitHub Actions](#apk-via-github-actions)
8. [Connect Nuvuja to IRIS](#connect-nuvuja-to-iris)
9. [Environment Variables Reference](#environment-variables-reference)

---

## Architecture Overview

```
                ┌──────────────────────────────────────────────┐
                │              IRIS Flask App (:5000)          │
                │  ┌────────────────────────────────────────┐  │
                │  │         Multi-LLM Router (4 backends)  │  │
                │  │  Aevibron │ Ollama │ Groq │ OpenAI     │  │
                │  └────────────────────────────────────────┘  │
                │  ┌────────────────────────────────────────┐  │
                │  │           OMNIS Skill Router             │  │
                │  │  100 capabilities across 10 categories  │  │
                │  └────────────────┬───────────────────────┘  │
                │  ┌─────────────────┴────────────────────┐   │
                │  │  30 Agents │ 11 Tools │ 7 Senses     │   │
                │  │  Cortex (7 reasoning modules)         │   │
                │  │  Memory (semantic+episodic+vector)   │   │
                │  │  Persona (identity+emotions+bond)    │   │
                │  └────────────────────────────────────────┘  │
                │  ┌────────────────────────────────────────┐  │
                │  │  Self-Healing Autonomous Loop          │  │
                │  │  plan → execute → verify → fix → retry  │  │
                │  └────────────────────────────────────────┘  │
                └──────────────────────────────────────────────┘
                                 ▲
                                 │ HTTP
                ┌────────────────┴───────────────────────────┐
                │              Clients                        │
                │  Nuvuja (web) │ Tauri app (desktop) │ APK  │
                └─────────────────────────────────────────────┘
```

---

## Deploy on Vercel

IRIS ships with `vercel.json` configured for the `@vercel/python` runtime.

### Steps

1. **Push IRIS to a GitHub repo** (or use the zip from `/home/z/my-project/download/IRIS.zip`)

2. **Import on Vercel**:
   - Go to https://vercel.com/new
   - Import your GitHub repo (or drag-and-drop the IRIS folder)
   - Vercel auto-detects the `vercel.json` config

3. **Set environment variables** (Vercel dashboard → Project → Settings → Environment Variables):
   ```
   IRIS_LLM_BACKEND=groq           # aevibron | ollama | groq | openai
   GROQ_API_KEY=gsk_your_key_here   # if backend=groq
   AEVIBRON_API_KEY=                # if backend=aevibron
   AEVIBRON_BASE_URL=https://aevibron-gateway.vercel.app/api/v1
   OLLAMA_HOST=http://localhost:11434   # if backend=ollama (won't work on Vercel — see below)
   OPENAI_API_KEY=                  # if backend=openai
   GITHUB_TOKEN=                    # for autonomous git operations
   VERCEL_TOKEN=                    # for autonomous deploys
   FLASK_SECRET_KEY=                # 32+ char random string
   ```

4. **Deploy**:
   ```bash
   vercel --prod --token $VERCEL_TOKEN
   ```

5. **Verify**:
   ```bash
   curl https://your-iris.vercel.app/health
   curl https://your-iris.vercel.app/api/llm/status
   curl -X POST https://your-iris.vercel.app/api/iris/autonomous \
     -H "Content-Type: application/json" \
     -d '{"task":"list files in /tmp"}'
   ```

### Vercel serverless limitations

- **Max 60s execution** (Pro: 300s, Enterprise: 900s) — long autonomous tasks may need chunking
- **No persistent filesystem** — `/tmp` is ephemeral. IRIS's SQLite memory DBs won't persist across cold starts. **For production, switch to PostgreSQL** (set `DATABASE_URL` env var)
- **No long-running shell processes** — `execute_shell` works but can't run interactive shells
- **Ollama won't work** — Vercel serverless can't reach `localhost:11434`. Use Groq or Aevibron or cloud OpenAI instead.
- **`screen_capture`/`webcam_capture` won't work** — no display hardware on serverless

### For always-on IRIS (persistent memory + proactive engine + 24/7)

Use a VPS (DigitalOcean, Hetzner, Railway, Fly.io, Modal) — these match Hermes's "always-on agent" architecture better than Vercel serverless.

---

## Deploy with Docker

IRIS ships with a `Dockerfile` (slimmed deps for fast builds).

```bash
# Build
docker build -t iris-agent .

# Run (with env vars from .env file)
docker run -d --name iris \
  -p 5000:5000 \
  --env-file .env \
  -v iris-data:/app/data \
  iris-agent

# Verify
curl http://localhost:5000/health
```

### Docker Compose (with Ollama sidecar)

```yaml
# docker-compose.yml
version: '3.8'
services:
  iris:
    build: .
    ports: ["5000:5000"]
    environment:
      - IRIS_LLM_BACKEND=ollama
      - OLLAMA_HOST=http://ollama:11434
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    depends_on: [ollama]
    volumes:
      - iris-data:/app/data
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama-models:/root/.ollama
    # On a GPU machine, uncomment:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           capabilities: [gpu]
volumes:
  iris-data:
  ollama-models:
```

```bash
docker-compose up -d
# Pull a model for Ollama
docker exec -it iris-ollama-1 ollama pull llama3.1
```

---

## Deploy on a VPS

For always-on IRIS with persistent memory + proactive engine:

### 1. Provision a VPS

- **DigitalOcean** droplet ($5/mo, 1GB RAM) — minimum
- **Hetzner** CX22 ($4.5/mo, 4GB RAM) — recommended (IRIS + Ollama)
- **Railway** / **Fly.io** — managed, easier deploys

### 2. Install IRIS

```bash
git clone https://github.com/yourusername/iris.git
cd iris
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-deploy.txt
```

### 3. Configure env

```bash
cp .env.example .env
# Edit .env — set IRIS_LLM_BACKEND, API keys, etc.
```

### 4. Run with systemd (always-on)

```bash
# /etc/systemd/system/iris.service
[Unit]
Description=IRIS Autonomous Agent
After=network.target

[Service]
Type=simple
User=iris
WorkingDirectory=/home/iris/iris
Environment=PYTHONPATH=/home/z/.local/lib/python3.13/site-packages
ExecStart=/home/iris/iris/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable iris
sudo systemctl start iris
sudo systemctl status iris
```

### 5. Optional: install Ollama for local LLM

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1
# Set IRIS_LLM_BACKEND=ollama in .env
```

### 6. Reverse proxy with Caddy (auto-HTTPS)

```Caddyfile
iris.yourdomain.com {
    reverse_proxy localhost:5000
}
```

---

## Multi-LLM Provider Setup

IRIS supports **4 LLM backends**, switchable via the `IRIS_LLM_BACKEND` env var:

| Backend | Use case | Setup |
|---|---|---|
| `aevibron` | Aevibron gateway (default) | Set `AEVIBRON_API_KEY` |
| `ollama` | Local, free, no API key | Install Ollama, `ollama pull llama3.1` |
| `groq` | Fast cloud (free tier) | Get key at https://console.groq.com |
| `openai` | Any OpenAI-compat cloud | Set `OPENAI_API_KEY` + optionally `OPENAI_BASE_URL` |

### Per-request backend override

```bash
# Use a different backend for one request
curl -X POST http://localhost:5000/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "groq",
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### List available models per backend

```bash
curl http://localhost:5000/api/llm/models?backend=groq
curl http://localhost:5000/api/llm/models?backend=ollama
```

---

## Wake Word + Always-On Architecture

### The challenge

Wake word ("Hey IRIS") requires **always-on audio capture**. A web page can't do this:
- Browser tabs sleep after inactivity
- Microphone requires user gesture to start
- Background audio capture drains battery on mobile

### Recommended architecture (the best option)

```
┌─────────────────────────────────────────────────────────┐
│                  IRIS Backend (VPS)                      │
│  Always-on Flask app + proactive engine + memory        │
│  Reachable at https://iris.yourdomain.com               │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTPS + WebSocket
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐
│ Tauri Desktop │ │   PWA Web   │ │   APK (later)│
│   Companion   │ │   (Nuvuja)  │ │  via Capacitor│
│              │ │              │ │              │
│ ✓ Wake word  │ │ ✓ Chat UI   │ │ ✓ Wake word  │
│ ✓ Floating   │ │ ✓ Code edit │ │ ✓ Background │
│   window     │ │ ✓ AI panel  │ │   service    │
│ ✓ Tray icon │ │ ✗ No wake   │ │ ✓ Push notif │
│ ✓ Global hot │ │   word     │ │              │
│   keys       │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Why Tauri for desktop (not Electron)

- **Tauri**: ~10-15MB binary, uses system webview, MIT licensed, Rust core
- **Electron**: ~100MB+ binary, bundles Chromium, heavy
- Tauri can run IRIS as a **sidecar process** (bundled Python) or connect to a remote IRIS instance

### Tauri app features

- **Tray icon** — IRIS runs in the background, click to open chat
- **Global hotkey** — e.g. `Cmd+Shift+I` opens the chat window from anywhere
- **Wake word** — uses `whisper-rs` or `porcupine` for offline "Hey IRIS" detection
- **Floating window** — always-on-top mini chat that hovers over other windows
- **Device control** — native screen capture, file ops, ADB for Android

### PWA web (Nuvuja)

- Already built — runs in any browser
- Installable as PWA (Add to Home Screen)
- **No wake word** (browser limitation) — but full chat + voice when active
- Uses Web Speech API for STT/TTS when the page is open

### APK via Capacitor + GitHub Actions (later phase)

When wake word + always-on is critical for mobile:

1. **Wrap Nuvuja PWA in Capacitor**:
   ```bash
   npm install @capacitor/core @capacitor/cli
   npx cap init
   npx cap add android
   npx cap open android
   ```

2. **Add a background service** for wake word detection (Android Foreground Service)

3. **GitHub Actions workflow** to compile the APK:
   ```yaml
   # .github/workflows/build-apk.yml
   name: Build APK
   on: push
   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: { node-version: 20 }
         - uses: actions/setup-java@v4
           with: { distribution: temurin, java-version: 17 }
         - run: npm ci
         - run: npm run build
         - run: npx cap sync android
         - run: cd android && ./gradlew assembleDebug
         - uses: actions/upload-artifact@v4
           with: { name: nuvuja-apk, path: android/app/build/outputs/apk/debug/*.apk }
   ```

4. **Users download the APK** from GitHub Releases (or Play Store later)

### My recommendation (in priority order)

1. **NOW**: Deploy IRIS on Vercel (free, fast) — gives you a public IRIS endpoint
2. **NOW**: Nuvuja web editor on Vercel — already running
3. **NEXT**: Tauri desktop companion — for wake word + floating window + always-on
4. **LATER**: APK via Capacitor + GitHub Actions — when mobile wake word is critical

---

## Connect Nuvuja to IRIS

Once IRIS is deployed (Vercel or VPS), Nuvuja connects via the LLM Router API:

### Nuvuja settings page (to be built)

```
┌─ Settings ─────────────────────────────────────────────┐
│                                                        │
│  IRIS Connection                                       │
│  ┌──────────────────────────────────┐ ✓ connected     │
│  │ https://iris.yourdomain.com       │                 │
│  └──────────────────────────────────┘                 │
│  Status: healthy · 30 agents · 100 capabilities        │
│                                                        │
│  ─────────────────────────────────────────────         │
│                                                        │
│  LLM Provider                                          │
│  ○ Aevibron-gateway   ○ Ollama (local)                │
│  ● Groq              ○ OpenAI-compatible              │
│                                                        │
│  API Key: gsk_•••••••••••••••••••••••••••••••••••     │
│  Model:   [llama-3.3-70b-versatile         ▾]         │
│                                                        │
│  [Test connection]  [Save]                              │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### API calls Nuvuja makes

```typescript
// 1. Check IRIS status
const status = await fetch(`${IRIS_URL}/api/llm/status`);
// → {default_backend, backends: {aevibron, ollama, groq, openai}}

// 2. List models for selected backend
const models = await fetch(`${IRIS_URL}/api/llm/models?backend=groq`);
// → {models: [{id: "llama-3.3-70b-versatile"}, ...]}

// 3. Test connection
const test = await fetch(`${IRIS_URL}/api/llm/chat`, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    backend: "groq",
    messages: [{role: "user", content: "Hello from Nuvuja!"}]
  })
});

// 4. All subsequent /api/chat calls in Nuvuja's AIPanel proxy through IRIS
//    with the user-selected backend
```

---

## Environment Variables Reference

See `.env.example` for the full list with comments. The critical ones:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `IRIS_LLM_BACKEND` | yes | `aevibron` | `aevibron` \| `ollama` \| `groq` \| `openai` |
| `IRIS_LLM_MODEL` | no | backend default | Default model for the active backend |
| `AEVIBRON_BASE_URL` | if aevibron | `https://aevibron-gateway.vercel.app/api/v1` | Aevibron gateway URL |
| `AEVIBRON_API_KEY` | if aevibron | — | Aevibron API key |
| `OLLAMA_HOST` | if ollama | `http://localhost:11434` | Local Ollama URL |
| `GROQ_API_KEY` | if groq | — | Groq API key (console.groq.com) |
| `OPENAI_API_KEY` | if openai | — | OpenAI or any OpenAI-compat key |
| `OPENAI_BASE_URL` | if openai | `https://api.openai.com/v1` | Override for OpenRouter, Together, etc. |
| `GITHUB_TOKEN` | for git ops | — | GitHub PAT for autonomous git operations |
| `VERCEL_TOKEN` | for deploys | — | Vercel token for autonomous deployments |
| `FLASK_SECRET_KEY` | prod | — | 32+ char random string |
| `PHONE_BRIDGE_ENABLED` | for ADB | `false` | Set `true` to enable Android control |
| `DEBUG` | dev | `false` | Flask debug mode |

---

## IRIS v2 Capability Count

- **30 agents** (all compile + register cleanly)
- **100 capabilities** across 10 categories:
  - 13 productivity (code generation, web scraping, charts, etc.)
  - 13 autonomous tools (git, shell, file, deploy, self-healing loop) — NEW
  - 5 device control (screen, webcam, SMS, contacts, photo) — NEW
  - 5 GitHub integration (issues, PRs, releases, repos) — NEW
  - 7 inbuilt apps (calendar, calculator, maps, file explorer) — NEW
  - 10 security (cybersecurity, forensics, OSINT, etc.)
  - 11 intelligence (research, memory, voice, etc.)
  - 10 utilities (calculator, weather, translation, etc.)
  - 10 personal productivity (tasks, alarms, reminders, etc.)
  - 7 media (image gen, audio transcription, etc.)
  - 4 communication (contacts, messaging, etc.)
  - 3 orchestration (consciousness, multi-agent, self-healing)
- **4 LLM backends** (Aevibron, Ollama, Groq, OpenAI)
- **11 tools** (git, docker, aws, nmap, etc.)
- **7 senses** (system monitor, file watcher, network watcher, etc.)
- **15 modules** all online (autonomous, consciousness, core, cortex, memory, omnis, orchestrator, persona, proactive, security, senses, skills, tools, vision, voice)
