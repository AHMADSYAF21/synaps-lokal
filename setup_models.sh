#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  setup_models.sh — Pull & Verify Ollama Models
#  Run this separately if you want to change models
# ═══════════════════════════════════════════════════════════════

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RESET='\033[0m'
info() { echo -e "${CYAN}[→]${RESET} $1"; }
log()  { echo -e "${GREEN}[✓]${RESET} $1"; }
warn() { echo -e "${YELLOW}[!]${RESET} $1"; }

# Check Ollama running
if ! pgrep -x "ollama" > /dev/null; then
  info "Starting Ollama..."
  ollama serve &>/dev/null &
  sleep 3
fi

# ── Model Options ─────────────────────────────────────────────
# Low RAM (4GB):   llama3:8b-instruct-q4_0  + deepseek-coder:1.3b
# Medium (8GB):    llama3                   + deepseek-coder:6.7b
# High (16GB+):    llama3:70b               + deepseek-coder:33b

RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "8")
info "Detected RAM: ~${RAM_GB}GB"

if   [ "$RAM_GB" -ge 16 ]; then
  GENERAL="llama3"
  CODER="deepseek-coder:6.7b"
elif [ "$RAM_GB" -ge 8 ]; then
  GENERAL="llama3:8b"
  CODER="deepseek-coder:6.7b"
else
  GENERAL="llama3:8b-instruct-q4_0"
  CODER="deepseek-coder:1.3b"
  warn "Low RAM detected — using quantized models (reduced quality)"
fi

EMBED="nomic-embed-text"

echo ""
info "Will pull:"
echo "  General : $GENERAL"
echo "  Coder   : $CODER"
echo "  Embed   : $EMBED"
echo ""

read -p "Continue? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then exit 0; fi

# ── Pull ──────────────────────────────────────────────────────
info "Pulling $GENERAL..."
ollama pull "$GENERAL"
log "$GENERAL ready"

info "Pulling $CODER..."
ollama pull "$CODER"
log "$CODER ready"

info "Pulling $EMBED..."
ollama pull "$EMBED"
log "$EMBED ready"

# ── Update .env ───────────────────────────────────────────────
ENV_FILE="$(dirname "$0")/../backend/.env"
if [ -f "$ENV_FILE" ]; then
  sed -i "s/^GENERAL_MODEL=.*/GENERAL_MODEL=$GENERAL/" "$ENV_FILE"
  sed -i "s/^CODER_MODEL=.*/CODER_MODEL=$CODER/"       "$ENV_FILE"
  log ".env updated with selected models"
fi

# ── Verify ────────────────────────────────────────────────────
echo ""
info "Installed models:"
ollama list

echo ""
log "All models ready! Run ./scripts/run.sh to start Synapse."
