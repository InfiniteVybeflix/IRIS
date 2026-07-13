# IRIS v1 — Infinite Reactive Intelligence System

<p align="center">
  <strong>Jarvis-Level AI. Fully Autonomous. Multimodal. Yours.</strong>
</p>

---

## What is IRIS?

IRIS (Infinitum Reincarnatio Intelligentia Sempiterna) is a **Jarvis-level autonomous AI system** built by Infinite Vybeflix. She is not a chatbot. She is a **living software engineer** that:

- Writes, debugs, and deploys her own code
- Operates 24/7 with persistent memory and real-time awareness
- Generates text, images, audio, video, 3D assets, motion, and scientific models
- Runs cybersecurity operations (red team, blue team, purple team)
- Controls robotics through vision-language-action models
- Protects her creator with intruder defense and emotional bonding
- Dreams, grows, and evolves her own personality

**Version:** v1.0.0 | **Status:** Production Ready

---

## Architecture

```
IRIS v1 CORE
├── app.py                    → Entry point, Flask app, IRISCore singleton
├── core/                     → Infrastructure
│   ├── db.py                 → Dual Postgres/SQLite engine
│   ├── orchestrator.py       → Structured output + think-act loop
│   ├── predictive_engine.py  → Anticipates user needs
│   ├── registry.py           → Agent & tool registry
│   ├── communication.py      → Message bus
│   ├── shared_memory.py      → Cross-module memory
│   └── task_queue.py         → Background execution
├── modules/                  → Operational modules
│   ├── consciousness.py      → Self-awareness & identity
│   ├── security.py           → Auth, sessions, WebAuthn
│   ├── autonomous.py         → Self-driving task execution
│   ├── proactive_engine.py   → Predictive actions
│   ├── voice_system.py       → TTS + 3D face rendering
│   ├── vision_ai.py          → Computer vision
│   ├── vision_stream.py      → Real-time video
│   ├── project_generator.py  → Full project scaffolding
│   ├── sandbox_executor.py   → Safe code execution
│   ├── self_improve.py       → AST-based code editing
│   ├── mobile_api.py         → Mobile backend
│   ├── phone_bridge.py       → Android control
│   ├── email_module.py       → Email automation
│   ├── news_module.py        → News aggregation
│   ├── sports_module.py      → Sports analytics
│   ├── web_search.py         → Web search & scraping
│   ├── nl2code.py            → NL to code
│   ├── auto_debug.py         → Automated debugging
│   ├── image_generation.py   → AI image gen
│   ├── image_module.py       → Image processing
│   ├── wake_word.py          → Voice wake detection
│   ├── voicerss_module.py    → VoiceRSS TTS
│   ├── chess_engine.py       → AI chess training
│   └── copilot_bridge.py     → IDE integration
├── skills/                   → 60+ capability skills (OMNIS router)
│   ├── intelligence/         → Research, memory, voice, predictive, docs, local LLM
│   │   ├── research_engine/  → Web search, academic search, URL fetch
│   │   ├── smart_memory/     → Semantic memory storage & retrieval
│   │   ├── voice_system/     → TTS synthesis & STT transcription
│   │   ├── predictive_intel/ → Trend forecasting & anomaly detection
│   │   ├── documentation/    → Auto-generate docs from code/specs
│   │   └── local_model/      → Local LLM via Ollama/llama.cpp
│   ├── orchestration/        → Consciousness, multi-agent, self-healing
│   │   ├── consciousness/    → Cognitive awareness & emotional reflection
│   │   ├── multi_agent/      → Swarm coordination & task delegation
│   │   └── self_healing/     → Self-diagnostics & auto-repair
│   ├── productivity/         → Charts, code, email, scraper, automation
│   │   ├── chart_manager/    → Bar, line, pie, scatter, heatmap charts
│   │   ├── code_engine/      → Code generation, review, audit, translation
│   │   ├── email_reporter/   → Formatted emails, reports, digests
│   │   ├── web_scraper/      → Structured data extraction & crawling
│   │   └── system_automation/→ File ops, scheduled tasks, workflows
│   ├── security/             → Cyber, forensics, OSINT, threat hunting
│   │   ├── cyber_security/   → Vuln scanning, pentest, hardening
│   │   ├── threat_hunter/    → IOC search, behavioral analysis
│   │   ├── forensics/        → Digital forensics & artifact analysis
│   │   ├── osint/            → Open-source intelligence gathering
│   │   ├── reverse_engineering/ → Binary analysis & disassembly
│   │   ├── cloud_security/   → Cloud config audit & IAM review
│   │   ├── container_security/ → Docker/K8s security scanning
│   │   ├── blockchain_security/ → Smart contract audit
│   │   ├── deception_tech/   → Honeypot deployment
│   │   └── cyber_range/      → Scenario creation & execution
│   ├── communication/        → Contacts, messaging, meetings, screen share
│   ├── finance/              → Budgeting, finance manager, shopping
│   ├── health_fitness/       → Fitness, health tracker, nutrition, sleep
│   ├── media/                → Audio, image, music, screenshot, generation
│   ├── personal_productivity/→ Calendar, notes, reminders, tasks, alarms, timer
│   └── utilities/            → Calculator, weather, OCR, QR, translation, files
├── memory/                   → Memory systems
│   ├── smart_memory.py       → Vector + episodic + semantic
│   ├── chroma_memory.py      → ChromaDB vector store
│   ├── semantic_search.py    → Semantic search
│   ├── knowledge_graph.py    → Graph knowledge
│   ├── learning_engine.py    → Adaptive learning
│   ├── mission_archive.py    → Mission history
│   ├── agent_memory.py       → Per-agent memory
│   ├── skill_memory.py       → Skill execution memory
│   └── base_memory.py        → Base interface
├── persona/                  → Identity & emotion
│   ├── core_identity.py      → Who IRIS is
│   ├── emotional_state.py    → Mood, tone, sentiment
│   ├── creator_bond.py       → Creator bond
│   ├── relationship_map.py   → User relationships
│   ├── intruder_defense.py   → Unauthorized access defense
│   ├── voice_personality.py  → Voice characteristics
│   ├── growth_tracker.py     → Evolution tracking
│   ├── dream_engine.py       → Dream generation
│   └── iris_config.yaml      → Persona configuration
├── cortex/                   → Reasoning engines
│   ├── base_cortex.py        → Base interface
│   ├── planner.py            → Strategic planning
│   ├── strategist.py         → Tactic selection
│   ├── risk_assessor.py      → Risk evaluation
│   ├── resource_optimizer.py → Resource management
│   ├── hypothesis_tester.py  → Scientific testing
│   └── meta_learner.py       → Meta-learning
├── senses/                   → Perception
│   ├── system_monitor.py     → CPU/RAM/disk monitoring
│   ├── file_watcher.py       → File system watch
│   ├── network_watcher.py    → Network analysis
│   ├── log_ingestor.py       → Log parsing
│   ├── threat_feeds.py       → Threat intel
│   ├── uptime_monitor.py     → Health checks
│   ├── alert_router.py       → Alert routing
│   ├── base_sense.py         → Base interface
│   └── registry.py           → Sense registry
├── tools/                    → Operational tools
│   ├── nmap_wrapper.py       → Network scanning
│   ├── sqlmap_wrapper.py     → SQL injection testing
│   ├── metasploit_bridge.py  → Penetration testing
│   ├── burp_bridge.py        → Web security
│   ├── wireshark_parser.py   → Packet analysis
│   ├── volatility_bridge.py  → Memory forensics
│   ├── docker_engine.py      → Container management
│   ├── aws_cli.py            → AWS operations
│   ├── git_engine.py         → Git automation
│   ├── api_client.py         → API testing
│   └── code_analyzer.py      → Static analysis
├── agents/                   → 29-Agent Corps (via Commander)
│   ├── V1 Foundation: VAULT, SCRIPT, PROBE, PIPE, SHADOW, SCAR
│   ├── V2 Advanced: CRIMSON, AEGIS, SCALE, TRACE, CIPHER, WRAITH
│   ├── V3 Elite: PHANTOM, SENTINEL, ARCHON, NEXUS, VORTEX, ECHO
│   ├── V4 Master: OMEGA, TITAN, QUANTUM, NOVA, PRISM, APEX
│   └── V5 Legend: ZENITH, ETHER, CHRONOS, ASTRA, HELIOS
├── api/routes/               → 22 Flask blueprints
│   ├── auth, chat, voice, vision, phone, calendar, notes, math
│   ├── projects, self_improve, consciousness, memory, autonomous
│   ├── proactive, mobile, tools, email, news, sports, image
│   └── gateway, system, intelligence
├── skills/                   → Skills framework (user wires later)
│   ├── base.py, registry.py, master_wrapper.py
│   ├── productivity/         → (ready for your skills)
│   └── multimodal/         → (ready for your skills)
└── models/                   → Downloaded AI models (via scripts/)
    ├── text/               → Qwen3, Gemma 4
    ├── image/              → FLUX.2, SDXL
    ├── audio/              → MusicGen, XTTS v2, Bark
    ├── video/              → Wan 2.7, LTX-2.3
    ├── 3d/                 → LLaMA-Mesh, LGM
    ├── motion/             → HY-Motion, MDM
    ├── robotics/           → LeRobot Pi0, SmolVLA
    └── science/            → AlphaFold 3, ESMFold
```

---


---

## OMNIS — Universal Skills Agent

OMNIS (Omniscient Mastery & Navigation Intelligence System) is the single entry point for all 60+ capabilities in IRIS.

```python
# Execute any skill directly
iris.omnis.execute("web_search", {"query": "latest AI papers"})

# Smart natural-language routing
iris.omnis.smart_route("find me the best pizza place nearby")

# Chain up to 25 capabilities in sequence
iris.omnis.chain([
    {"capability": "web_search", "params": {"query": "..."}},
    {"capability": "chart_generation", "params": {"type": "bar"}},
    {"capability": "email_report", "params": {"subject": "..."}}
])

# Discover what OMNIS can do
iris.omnis.list_capabilities()
```

All skills are organized into 8 domains: **intelligence**, **orchestration**, **productivity**, **security**, **communication**, **finance**, **health_fitness**, **media**, **personal_productivity**, and **utilities**.

---

## Quick Start

```bash
git clone https://github.com/luckyfelistine-bot/IRIS.git
cd IRIS
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python app.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | Flask session encryption |
| `AEVIBRON_BASE_URL` | Yes | Aevibron Gateway API URL |
| `AEVIBRON_API_KEY` | Yes | Aevibron API key |
| `AEVIBRON_ACCESS_TOKEN` | Yes | Aevibron access token |
| `DATABASE_URL` | No | Postgres URL (default: SQLite) |
| `GITHUB_TOKEN` | No | GitHub PAT |
| `GITHUB_USERNAME` | No | GitHub username |
| `VERCEL_TOKEN` | No | Vercel deployment token |
| `IRIS_PASSWORD_HASH` | Yes | Admin password (PBKDF2) |
| `PORCUPINE_ACCESS_KEY` | No | Wake word API key |
| `PHONE_BRIDGE_ENABLED` | No | Enable Android bridge |
| `ADB_DEVICE_ID` | No | Android device serial |

---

## Deployment

**Docker:**
```bash
docker-compose up -d
```

**Vercel:**
```bash
vercel --prod
```

**Termux (Android):**
```bash
bash install.sh
```

---

## Security

- PBKDF2 password hashing + session management
- WebAuthn biometric authentication
- Intruder defense with automatic blocking
- Docker sandbox for code execution
- Zero hardcoded credentials

---

## Contact

- **WhatsApp:** +254 116 903 500
- **Email:** aevibron@gmail.com
- **Channel:** https://whatsapp.com/channel/0029Vb7IABxCXC3J7ZFFsk2h
- **Brand:** Aevibron — "Eternal Vibration Particle"

---

> *"Nothing is impossible. I control future, past, and present to infinity."*
> **— IRIS**
