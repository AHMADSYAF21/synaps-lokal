<div align="center">

# ◈ SYNAPSE LOCAL v3

**Autonomous Self-Improving AI — 100% Offline**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)](https://react.dev)
[![Electron](https://img.shields.io/badge/Electron-31-47848f?logo=electron&logoColor=white)](https://electronjs.org)
[![Capacitor](https://img.shields.io/badge/Capacitor-6-119eff?logo=capacitor&logoColor=white)](https://capacitorjs.com)
[![Ollama](https://img.shields.io/badge/Ollama-LLaMA3-000?logo=ollama&logoColor=white)](https://ollama.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

*Runs on Windows · macOS · Linux · Android · Termux*

</div>

---

## What is Synapse Local?

Synapse Local is a fully autonomous AI system that runs **100% offline** on your own hardware — no API keys, no cloud, no subscriptions. It can:

- 💬 **Chat** with streaming responses using local LLMs (Llama 3, DeepSeek Coder)
- 🧠 **Reason** using Chain-of-Thought, Tree-of-Thought, and Self-Reflection
- 📋 **Plan** complex multi-step tasks automatically
- 🔧 **Write new tools** for itself when it detects a capability gap
- 📚 **Learn skills** from every successful interaction
- ⟳ **Improve code** iteratively with automatic critique and strategy switching
- 🩺 **Heal itself** with a background health monitor that auto-repairs components
- 📱 **Run as** a Desktop app (Electron) or Android APK (Capacitor)

---

## Quick Start

```bash
git clone https://github.com/AHMADSYAF21/synapse-local.git
cd synapse-local
chmod +x scripts/*.sh build.sh
./scripts/install.sh   # ~15 min (downloads AI models)
./scripts/run.sh       # starts all services
# → Open http://localhost:3000
```

> **Requirements:** Python 3.10+, Node.js 18+, 8GB+ RAM, [Ollama](https://ollama.com)

---

## Build Desktop App or Android APK

```bash
# Desktop app (.exe / .dmg / .AppImage):
./build.sh desktop

# Android APK (needs Java JDK 17 + Android SDK):
./build.sh android

# Run desktop in dev mode (no installer):
./build.sh run
```

See [INSTALL.md](INSTALL.md) for detailed platform instructions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   SYNAPSE LOCAL v3                      │
│                                                         │
│  Frontend (React + Vite)                                │
│  7 panels: Chat · Planner · Improve · Memory            │
│            Skills · Capabilities · System               │
│                     │                                   │
│                     ▼  REST + SSE                       │
│  Backend (FastAPI, port 8000)                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Meta-Agent  ← auto-routes every request        │   │
│  │   ├── Reasoning Engine (CoT / ToT / Reflect)   │   │
│  │   ├── Multi-Step Planner                       │   │
│  │   ├── Agent Orchestrator (4 roles)             │   │
│  │   └── Self-Improvement Loop v2                 │   │
│  │                                                │   │
│  │ Capability Engine  ← AI writes new tools       │   │
│  │ Skill Library      ← learns from interactions  │   │
│  │ Vector Memory      ← ChromaDB semantic search  │   │
│  │ Self-Healing       ← background health monitor │   │
│  └─────────────────────────────────────────────────┘   │
│                     │                                   │
│  Ollama (port 11434) — llama3 · deepseek-coder         │
└─────────────────────────────────────────────────────────┘

Desktop: Electron wraps everything into a single .exe/.dmg/.AppImage
Android: Capacitor wraps the React UI into an APK (connects to backend)
```

---

## File Structure

```
synapse-local/
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # 30+ API endpoints
│   ├── config.py               # Environment configuration
│   ├── requirements.txt
│   └── core/
│       ├── meta_agent.py       # Top-level autonomous orchestrator
│       ├── reasoning.py        # CoT · ToT · Reflection · Decompose
│       ├── agents.py           # Multi-role agents (ReAct loop)
│       ├── planner.py          # Multi-step plan & execute
│       ├── capability_engine.py# AI writes new Python tools
│       ├── skill_library.py    # Learn · Store · Retrieve skills
│       ├── self_heal.py        # Background health monitor
│       ├── self_improve_v2.py  # Iterative code improvement
│       ├── memory.py           # ChromaDB vector memory
│       ├── llm.py              # Ollama interface + streaming
│       └── tools.py            # Built-in tools (code, file, terminal, web)
│
├── frontend/                   # React + Vite UI
│   ├── src/
│   │   ├── App.jsx             # 7-panel layout, Electron + Android aware
│   │   ├── App.css             # Industrial terminal design system
│   │   ├── api/client.js       # Multi-platform API client
│   │   ├── hooks/useChat.js    # SSE streaming + MetaAgent events
│   │   └── components/
│   │       ├── Chat.jsx        # Streaming chat with Meta-AI toggle
│   │       ├── SkillPanel.jsx  # Skill library browser
│   │       ├── CapabilityPanel.jsx  # AI tool creator
│   │       ├── SystemPanel.jsx # Health monitor + reasoning tester
│   │       ├── MemoryPanel.jsx # Semantic memory explorer
│   │       └── AndroidSettings.jsx  # Backend URL config for Android
│   ├── capacitor.config.json   # Android/iOS Capacitor config
│   └── vite.config.js          # Multi-mode build (web/electron/android)
│
├── desktop/                    # Electron desktop app
│   ├── main.js                 # Main process: boots Python, Ollama, tray
│   ├── preload.js              # IPC bridge (contextBridge)
│   ├── splash.html             # Animated startup splash screen
│   ├── package.json            # electron-builder config
│   └── assets/                 # App icons
│
├── scripts/
│   ├── install.sh              # Auto-install all dependencies
│   ├── run.sh                  # Start all services
│   ├── setup_models.sh         # Pull/switch Ollama models
│   └── test_system.py          # 10-section test suite
│
├── build.sh                    # One-command build for desktop/android
├── docker-compose.yml          # Docker deployment
├── .env.example                # Environment variables template
├── .gitignore
├── LICENSE
├── README.md
└── INSTALL.md                  # Detailed build instructions
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System status + all stats |
| POST | `/chat` | Streaming chat (SSE) |
| POST | `/reasoning/think` | CoT / ToT / Reflect |
| POST | `/reasoning/decompose` | Break task into subtasks |
| POST | `/plan` | Multi-step plan + execute |
| POST | `/improve` | Self-improvement loop v2 |
| POST | `/capability/detect` | Check if new tool needed |
| POST | `/capability/expand` | Auto-create new tool |
| POST | `/capability/create` | Manually create tool |
| POST | `/skills/learn` | Teach a skill manually |
| POST | `/skills/search` | Semantic skill search |
| POST | `/skills/distill` | Distill knowledge |
| GET | `/healing/status` | Health monitor status |
| GET | `/evolution` | Interaction history |
| POST | `/tools/run` | Execute any tool |

Full API docs available at `http://localhost:8000/docs` (Swagger UI).

---

## AI Models Used

| Model | Purpose | Size |
|-------|---------|------|
| `llama3` / `llama3:8b` | General reasoning, planning, chat | 4–8 GB |
| `deepseek-coder` | Code generation and debugging | 4–7 GB |
| `nomic-embed-text` | Vector embeddings for memory | 0.3 GB |

The installer automatically selects quantized models for low-RAM devices (<8GB).

---

## How Self-Improvement Works

```
User request
     ↓
[Meta-Agent] analyzes → picks strategy: direct / plan / improve / research
     ↓
[Skill Library] injects relevant learned patterns into context
     ↓
[Execution] Agent / Planner / Reasoning Engine
     ↓
[Learning] skill extracted → stored → used in future requests
     ↓
[Capability Engine] if tool missing → AI writes Python class → registers it
     ↓
[Evolution Log] records every interaction for meta-learning
     ↓ (every 60 seconds)
[Self-Healing] monitors Ollama + ChromaDB → auto-repairs failures
```

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
