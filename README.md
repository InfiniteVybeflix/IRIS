# IRIS v2 — Infinite Reactive Intelligence System

> Autonomous AI agent system with 30 agents, 100 capabilities, multi-LLM
> provider routing, self-healing autonomous loop, device control, GitHub
> integration, and inbuilt apps (calendar, calculator, maps, file explorer).

## Quick Start

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure (optional — can configure from UI after deploy)
cp .env.example .env

# 3. Run
python app.py

# 4. Open settings to configure your LLM provider
#    http://localhost:5000/settings
```

## Settings UI

After deploying, visit `/settings` to configure:

- **LLM Provider** (pick one):
  - Auto-Select (IRIS picks the best available)
  - Aevibron Gateway (recommended)
  - Ollama Local (free, no API key)
  - Ollama Cloud
  - Groq
  - OpenAI / OpenAI-compatible
  - Custom (any URL + key + model)

- **Test Connection** — lists available models + sends a test prompt
- **Integrations** (all optional):
  - GitHub token (for autonomous git ops)
  - Vercel token (for autonomous deploys)
  - Cloudflare token (for CF Pages deploys)

All keys are masked when returned. No key is required for IRIS to work.

## Deploy to Vercel

1. Push to GitHub
2. Import on vercel.com/new
3. Set env vars (see `.env.example`)
4. Deploy
5. Visit `https://your-iris.vercel.app/settings` to configure

## Structure

```
IRIS/
├── app.py                    # Flask entry point (all routes registered)
├── config.py                 # Configuration (reads from .env)
├── vercel.json               # Vercel serverless config
├── Dockerfile               # Docker deployment
├── requirements.txt          # Slimmed deps (Vercel-compatible)
├── .env.example              # All env vars documented
├── .gitignore                # Prevents runtime files from being committed
├── DEPLOY.md                 # Full deployment guide
│
├── agents/                   # 30 agents (all compile cleanly)
├── core/                     # Core infrastructure
│   ├── llm_router.py         # Multi-LLM router (6 providers + auto-select)
│   ├── runtime.py            # IRIS singleton accessor
│   ├── orchestrator.py       # LLM-driven reasoning loop
│   ├── tool_registry.py      # 11 tools (git, docker, aws, nmap, etc.)
│   └── ...
│
├── modules/                  # Functional modules
│   ├── autonomous_loop.py    # Self-healing loop (plan→execute→verify→fix→retry)
│   ├── settings_manager.py   # Encrypted key storage + provider config
│   └── ...
│
├── skills/                   # 67 categorized skills (10 categories)
│   ├── productivity/         # code_engine, autonomous_tools, github_integration
│   ├── media/                # device_control, image_generation
│   ├── utilities/            # inbuilt_apps (calendar, calculator, maps)
│   ├── security/             # cyber_security, forensics, OSINT
│   └── ...
│   ├── calendar_skill.py     # Flask blueprint adapter (not a duplicate)
│   ├── math_skill.py         # Flask blueprint adapter
│   └── notes_skill.py        # Flask blueprint adapter
│
├── api/routes/               # Flask blueprints
│   └── settings.py           # Settings API (GET/POST/test/providers)
│
├── templates/
│   └── settings.html         # Settings UI page
│
├── static/                   # CSS, JS, fonts, 3D model, icons
├── persona/                  # Identity, emotions, creator bond
├── cortex/                   # 7 reasoning modules (planner, strategist, etc.)
├── senses/                   # 7 perceptual monitors
├── tools/                    # 11 operational tools
└── memory/                   # Semantic, episodic, vector, knowledge graph
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (30 agents, 100 capabilities) |
| GET | `/settings` | Settings UI page |
| GET | `/api/iris/settings` | Get current settings (keys masked) |
| POST | `/api/iris/settings` | Save settings |
| POST | `/api/iris/settings/test` | Test provider connection |
| GET | `/api/iris/settings/providers` | List all providers + fields |
| GET | `/api/llm/status` | LLM router status |
| GET | `/api/llm/models?backend=X` | List models for a backend |
| POST | `/api/llm/chat` | Chat with a specific backend (streaming SSE) |
| POST | `/api/iris/autonomous` | Self-healing autonomous task loop |
| POST | `/api/omnis/execute` | Execute any of 100 capabilities |
| GET | `/api/omnis/agents` | List 30 agents |
| GET | `/api/omnis/manifest` | List 100 capabilities |

## LLM Providers

| Provider | Key Required | Setup |
|----------|-------------|-------|
| Aevibron (recommended) | Yes | Set URL + key from Settings UI |
| Ollama Local | No | Install Ollama, pull a model |
| Ollama Cloud | Optional | Set URL from Settings UI |
| Groq | Yes | Get key at console.groq.com |
| OpenAI | Yes | Set URL + key from Settings UI |
| Custom | Optional | Any OpenAI-compatible endpoint |
| Auto-Select | — | IRIS probes all and picks first working |

## License

Proprietary — Aevibron.
