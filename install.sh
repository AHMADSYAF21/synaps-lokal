#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  SYNAPSE LOCAL v3 — Master Install Script
#  Supports: Termux (Android), Ubuntu/Debian, Arch Linux
# ═══════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[→]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║  SYNAPSE LOCAL v3 — INSTALLER        ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Detect Environment ────────────────────────────────────
detect_env() {
  if [ -d "/data/data/com.termux" ]; then
    ENV="termux"; log "Detected: Termux (Android)"
  elif [ -f "/etc/arch-release" ]; then
    ENV="arch"; log "Detected: Arch Linux"
  elif [ -f "/etc/debian_version" ]; then
    ENV="debian"; log "Detected: Debian/Ubuntu"
  else
    ENV="generic"; warn "Unknown OS — attempting generic install"
  fi
}

# ── Install System Packages ───────────────────────────────
install_deps() {
  info "Installing system dependencies…"
  case $ENV in
    termux)
      pkg update -y -q
      pkg install -y python nodejs git curl wget 2>/dev/null || true
      pip install --upgrade pip -q
      ;;
    debian)
      sudo apt-get update -y -q
      sudo apt-get install -y -q python3 python3-pip python3-venv \
        nodejs npm git curl wget build-essential 2>/dev/null || true
      ;;
    arch)
      sudo pacman -Syu --noconfirm -q python python-pip nodejs npm git curl 2>/dev/null || true
      ;;
    *)
      warn "Ensure Python 3.10+, Node.js 18+, git, curl are installed"
      ;;
  esac
  log "System dependencies ready"
}

# ── Install Ollama ────────────────────────────────────────
install_ollama() {
  info "Checking Ollama…"
  if command -v ollama &>/dev/null; then
    log "Ollama already installed ($(ollama --version 2>/dev/null || echo 'version unknown'))"
    return
  fi

  if [ "$ENV" = "termux" ]; then
    ARCH="$(uname -m)"
    case $ARCH in
      aarch64) BINARY="ollama-linux-arm64" ;;
      x86_64)  BINARY="ollama-linux-amd64" ;;
      *)        err "Unsupported arch: $ARCH" ;;
    esac
    VER="0.3.6"
    info "Downloading Ollama $VER for $ARCH…"
    curl -fsSL \
      "https://github.com/ollama/ollama/releases/download/v${VER}/${BINARY}" \
      -o "$PREFIX/bin/ollama" && chmod +x "$PREFIX/bin/ollama"
  else
    info "Installing Ollama via official script…"
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  log "Ollama installed"
}

# ── Python Backend Setup ──────────────────────────────────
setup_backend() {
  info "Setting up Python backend…"
  cd "$ROOT/backend"

  if [ "$ENV" = "termux" ]; then
    pip install -q -r requirements.txt
  else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
  fi

  # Create data directories
  mkdir -p ./data/chroma ./data/capabilities ./workspace
  log "Backend ready"
}

# ── Frontend Setup ────────────────────────────────────────
setup_frontend() {
  info "Setting up React frontend…"
  cd "$ROOT/frontend"
  npm install --silent
  log "Frontend ready"
}

# ── Create .env Files ─────────────────────────────────────
create_env() {
  info "Creating environment config…"

  cat > "$ROOT/backend/.env" << ENV
OLLAMA_BASE_URL=http://localhost:11434
GENERAL_MODEL=llama3
CODER_MODEL=deepseek-coder
EMBEDDING_MODEL=nomic-embed-text
CHROMA_PATH=./data/chroma
SKILL_DB_PATH=./data/skills.db
CAPABILITIES_DIR=./data/capabilities
EVOLUTION_LOG_PATH=./data/evolution.jsonl
MAX_MEMORY_RESULTS=5
MAX_ITERATIONS=5
TOOL_TIMEOUT=30
HEAL_INTERVAL_SEC=60
HOST=0.0.0.0
PORT=8000
ALLOWED_DIRS=./workspace
MAX_CODE_RUNTIME=20
AUTO_EXPAND_ON_FAIL=true
ENV

  cat > "$ROOT/frontend/.env" << ENV
VITE_API_URL=http://localhost:8000
ENV

  log ".env files created"
}

# ── Pull Models ───────────────────────────────────────────
pull_models() {
  info "Starting Ollama to pull models…"

  if ! pgrep -x "ollama" > /dev/null 2>&1; then
    ollama serve > /tmp/ollama_install.log 2>&1 &
    sleep 3
  fi

  # Auto-select model tier by RAM
  RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "8")
  info "Detected RAM: ~${RAM_GB}GB"

  if   [ "${RAM_GB:-8}" -ge 16 ]; then
    GENERAL="llama3"; CODER="deepseek-coder:6.7b"
  elif [ "${RAM_GB:-8}" -ge 8 ]; then
    GENERAL="llama3:8b"; CODER="deepseek-coder:6.7b"
  else
    GENERAL="llama3:8b-instruct-q4_0"; CODER="deepseek-coder:1.3b"
    warn "Low RAM — using quantized models"
  fi

  info "Pulling $GENERAL (general reasoning)…"
  ollama pull "$GENERAL" || warn "llama3 pull failed — try: ollama pull llama3:8b"

  info "Pulling $CODER (coding)…"
  ollama pull "$CODER"   || warn "deepseek-coder pull failed"

  info "Pulling nomic-embed-text (embeddings)…"
  ollama pull nomic-embed-text || warn "embed model pull failed"

  # Update .env with selected models
  sed -i "s/^GENERAL_MODEL=.*/GENERAL_MODEL=$GENERAL/" "$ROOT/backend/.env"
  sed -i "s/^CODER_MODEL=.*/CODER_MODEL=$CODER/"       "$ROOT/backend/.env"
  log "Models ready: $GENERAL + $CODER"
}

# ── Make scripts executable ───────────────────────────────
setup_scripts() {
  chmod +x "$ROOT/scripts/"*.sh
  log "Scripts made executable"
}

# ── Main ──────────────────────────────────────────────────
main() {
  detect_env
  install_deps
  install_ollama
  setup_backend
  setup_frontend
  create_env
  pull_models
  setup_scripts

  echo ""
  echo -e "${BOLD}${GREEN}"
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║   ✅  INSTALL COMPLETE!              ║"
  echo "  ╠══════════════════════════════════════╣"
  echo "  ║  Start:  ./scripts/run.sh            ║"
  echo "  ║  UI:     http://localhost:3000       ║"
  echo "  ║  API:    http://localhost:8000       ║"
  echo "  ║  Test:   python3 scripts/test_system.py ║"
  echo "  ╚══════════════════════════════════════╝"
  echo -e "${NC}"
}

main "$@"
