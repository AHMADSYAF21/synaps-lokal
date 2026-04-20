#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  SYNAPSE LOCAL — Build Script
#  Builds: Desktop app (Electron) + Android APK (Capacitor)
#  Usage:  ./build.sh [desktop|android|all]
# ═══════════════════════════════════════════════════════════════════
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$ROOT/frontend"
DESKTOP="$ROOT/desktop"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${GREEN}[✓]${RESET} $1"; }
info() { echo -e "${CYAN}[→]${RESET} $1"; }
warn() { echo -e "${YELLOW}[!]${RESET} $1"; }
err()  { echo -e "${RED}[✗]${RESET} $1"; exit 1; }

TARGET="${1:-all}"

echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   SYNAPSE LOCAL — BUILD SYSTEM        ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# ── Check prerequisites ───────────────────────────────────────────
check_prereqs() {
  info "Checking prerequisites…"
  command -v node  >/dev/null || err "Node.js not installed"
  command -v npm   >/dev/null || err "npm not installed"
  command -v python3 >/dev/null || err "python3 not installed"
  NODE_VER=$(node --version | sed 's/v//' | cut -d. -f1)
  [ "$NODE_VER" -ge 18 ] || err "Node.js 18+ required (found $NODE_VER)"
  log "Prerequisites OK (Node $(node --version))"
}

# ── Build React frontend ──────────────────────────────────────────
build_frontend_for() {
  local MODE="$1"
  info "Building React frontend [mode=$MODE]…"
  cd "$FRONTEND"
  npm install --silent
  npm run "build:$MODE"
  log "Frontend build complete → frontend/dist/"
}

# ═══════════════════════════════════════════════════════════════════
# DESKTOP BUILD (Electron → .exe / .dmg / .AppImage)
# ═══════════════════════════════════════════════════════════════════
build_desktop() {
  echo -e "\n${BOLD}${CYAN}── DESKTOP BUILD (Electron) ──────────────────${RESET}"

  check_prereqs
  build_frontend_for "electron"

  info "Installing Electron dependencies…"
  cd "$DESKTOP"
  npm install --silent

  # Detect platform
  PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$PLATFORM" in
    linux)  BUILD_CMD="npm run build:linux"  ;;
    darwin) BUILD_CMD="npm run build:mac"    ;;
    msys*|cygwin*|mingw*) BUILD_CMD="npm run build:win" ;;
    *)      BUILD_CMD="npm run build:linux"  ;;
  esac

  info "Running electron-builder ($PLATFORM)…"
  $BUILD_CMD

  DIST_DIR="$ROOT/dist-electron"
  echo ""
  log "Desktop build complete!"
  echo -e "  Output: ${CYAN}$DIST_DIR/${RESET}"
  ls "$DIST_DIR"/ 2>/dev/null | grep -E "\.(exe|dmg|AppImage|deb)" || true
}

# ═══════════════════════════════════════════════════════════════════
# ANDROID BUILD (Capacitor → APK)
# ═══════════════════════════════════════════════════════════════════
build_android() {
  echo -e "\n${BOLD}${CYAN}── ANDROID BUILD (Capacitor) ─────────────────${RESET}"

  check_prereqs

  # Check Java
  if ! command -v java >/dev/null; then
    err "Java JDK not found. Install with:\n  Ubuntu: sudo apt install openjdk-17-jdk\n  macOS: brew install openjdk@17"
  fi
  log "Java: $(java -version 2>&1 | head -1)"

  # Check Android SDK / ANDROID_HOME
  if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
    warn "ANDROID_HOME not set. Common paths:"
    warn "  Linux: ~/Android/Sdk"
    warn "  macOS: ~/Library/Android/sdk"
    warn "  Set with: export ANDROID_HOME=~/Android/Sdk"
    warn "  Or install Android Studio and set the SDK path"
    read -p "Enter Android SDK path (or press Enter to skip): " SDK_PATH
    if [ -n "$SDK_PATH" ]; then
      export ANDROID_HOME="$SDK_PATH"
      export PATH="$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools:$PATH"
    else
      err "Android SDK required for APK build"
    fi
  fi

  build_frontend_for "android"

  cd "$FRONTEND"

  # Add Android platform if not present
  if [ ! -d "android" ]; then
    info "Adding Android platform…"
    npx cap add android
  fi

  # Sync web assets
  info "Syncing assets to Android…"
  npx cap sync android

  # Build APK
  info "Building debug APK…"
  cd android
  chmod +x gradlew
  ./gradlew assembleDebug --quiet

  APK_PATH="$FRONTEND/android/app/build/outputs/apk/debug/app-debug.apk"
  if [ -f "$APK_PATH" ]; then
    # Copy to dist folder
    mkdir -p "$ROOT/dist-android"
    cp "$APK_PATH" "$ROOT/dist-android/SynapseLocal-debug.apk"
    echo ""
    log "Android APK built!"
    echo -e "  APK: ${CYAN}$ROOT/dist-android/SynapseLocal-debug.apk${RESET}"
    ls -lh "$ROOT/dist-android/SynapseLocal-debug.apk"
  else
    err "APK not found at $APK_PATH"
  fi
}

# ── Release APK (signed) ──────────────────────────────────────────
build_android_release() {
  echo -e "\n${BOLD}${CYAN}── ANDROID RELEASE APK ────────────────────────${RESET}"
  warn "For release APK, you need a keystore file."
  warn "Generate one with:"
  warn "  keytool -genkey -v -keystore synapse.keystore \\"
  warn "    -alias synapse -keyalg RSA -keysize 2048 -validity 10000"
  echo ""
  cd "$FRONTEND/android"
  ./gradlew assembleRelease
  APK="$FRONTEND/android/app/build/outputs/apk/release/app-release.apk"
  [ -f "$APK" ] && { cp "$APK" "$ROOT/dist-android/SynapseLocal-release.apk"; log "Release APK: dist-android/SynapseLocal-release.apk"; }
}

# ═══════════════════════════════════════════════════════════════════
# QUICK RUN (no build needed)
# ═══════════════════════════════════════════════════════════════════
run_desktop_dev() {
  echo -e "\n${BOLD}${CYAN}── RUN DESKTOP (dev mode) ─────────────────────${RESET}"
  check_prereqs
  cd "$FRONTEND" && npm install --silent
  build_frontend_for "electron"
  cd "$DESKTOP"  && npm install --silent
  info "Launching Electron app…"
  npm start
}

# ── Main ──────────────────────────────────────────────────────────
mkdir -p "$ROOT/dist-electron" "$ROOT/dist-android"

case "$TARGET" in
  desktop)         build_desktop ;;
  android)         build_android ;;
  android:release) build_android && build_android_release ;;
  run)             run_desktop_dev ;;
  all)
    build_desktop
    echo ""
    build_android
    ;;
  *)
    echo "Usage: $0 [desktop|android|android:release|run|all]"
    echo ""
    echo "  desktop   — Build Electron app (.exe/.dmg/.AppImage)"
    echo "  android   — Build Android debug APK"
    echo "  run       — Run Electron in dev mode"
    echo "  all       — Build both"
    exit 1
    ;;
esac

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   ✅  BUILD COMPLETE!                 ║"
echo "  ╠═══════════════════════════════════════╣"
echo "  ║  Desktop → dist-electron/             ║"
echo "  ║  Android → dist-android/              ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"
