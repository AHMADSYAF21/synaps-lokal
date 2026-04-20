#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  SYNAPSE LOCAL v3 — Run All Services
#  Starts: Ollama → Backend → Frontend
# ═══════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'

info() { echo -e "${CYAN}[→]${NC} $1"; }
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

PIDS=()

cleanup() {
  echo ""; warn "Stopping all services…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Ollama ────────────────────────────────────────────────
start_ollama() {
  if pgrep -x "ollama" > /dev/null 2>&1; then
    log "Ollama already running"; return
  fi
  info "Starting Ollama…"
  mkdir -p "$ROOT/logs"
  ollama serve > "$ROOT/logs/ollama.log" 2>&1 &
  PIDS+=($!)
  sleep 2
  log "Ollama started (port 11434)"
}

# ── Backend ───────────────────────────────────────────────
start_backend() {
  info "Starting FastAPI backend…"
  cd "$BACKEND"
  [ -d ".venv" ] && source .venv/bin/activate || true
  [ -f ".env"  ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true
  mkdir -p "$ROOT/logs" ./data/chroma ./data/capabilities ./workspace

  uvicorn main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --reload \
    --log-level info \
    > "$ROOT/logs/backend.log" 2>&1 &
  PIDS+=($!)

  info "Waiting for backend to be ready…"
  for i in $(seq 1 25); do
    curl -s "http://localhost:${PORT:-8000}/health" > /dev/null 2>&1 && {
      log "Backend ready (port ${PORT:-8000})"; return
    }
    sleep 1
  done
  warn "Backend slow to start — check logs/backend.log"
}

# ── Frontend ──────────────────────────────────────────────
start_frontend() {
  info "Starting React frontend…"
  cd "$FRONTEND"
  npm run dev > "$ROOT/logs/frontend.log" 2>&1 &
  PIDS+=($!)
  sleep 2
  log "Frontend ready (port 3000)"
}

# ── Status ────────────────────────────────────────────────
print_status() {
  echo ""
  echo -e "${BOLD}${GREEN}"
  echo "  ╔════════════════════════════════════════╗"
  echo "  ║   🧠  SYNAPSE LOCAL v3 IS RUNNING      ║"
  echo "  ╠════════════════════════════════════════╣"
  echo "  ║                                        ║"
  echo "  ║  🌐  UI     → http://localhost:3000    ║"
  echo "  ║  ⚡  API    → http://localhost:8000    ║"
  echo "  ║  🤖  Ollama → http://localhost:11434   ║"
  echo "  ║                                        ║"
  echo "  ║  Logs: ./logs/                         ║"
  echo "  ║  Press Ctrl+C to stop all services     ║"
  echo "  ╚════════════════════════════════════════╝"
  echo -e "${NC}"
}

mkdir -p "$ROOT/logs"
start_ollama
start_backend
start_frontend
print_status
wait
