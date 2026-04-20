# SYNAPSE LOCAL v3 — INSTALL & BUILD GUIDE

## Cara Cepat Jalankan (tanpa build)

```bash
git clone <repo> synapse-local && cd synapse-local
chmod +x scripts/*.sh build.sh
./scripts/install.sh    # install Python, Ollama, Node
./scripts/run.sh        # jalankan semua service
# Buka browser: http://localhost:3000
```

---

## BUILD DESKTOP APP (.exe / .dmg / .AppImage)

### Persiapan
```bash
# Butuh: Node.js 18+, npm, Python 3.10+
node --version   # harus >= 18
python3 --version
```

### Build
```bash
chmod +x build.sh
./build.sh desktop
# Output: dist-electron/
#   Windows → Synapse-Local-Setup-3.0.0.exe
#   macOS   → Synapse-Local-3.0.0.dmg
#   Linux   → Synapse-Local-3.0.0.AppImage
```

### Jalankan (dev, tanpa build installer)
```bash
./build.sh run
# Electron window terbuka langsung
```

### Windows (via PowerShell)
```powershell
# Install Node.js dari https://nodejs.org
# Install Python dari https://python.org
cd synapse-local
npm install --prefix frontend
npm run build:electron --prefix frontend
cd desktop && npm install
npx electron .
```

---

## BUILD ANDROID APK

### Persiapan
```bash
# 1. Install Java JDK 17
sudo apt install openjdk-17-jdk        # Ubuntu
brew install openjdk@17                # macOS

# 2. Install Android Studio atau Android Command-line Tools
# Download: https://developer.android.com/studio
# Set SDK path:
export ANDROID_HOME=~/Android/Sdk
export PATH=$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools:$PATH

# 3. Install SDK components
sdkmanager "platforms;android-34" "build-tools;34.0.0"
```

### Build APK Debug
```bash
./build.sh android
# Output: dist-android/SynapseLocal-debug.apk
```

### Install ke HP Android
```bash
# Via USB (USB debugging aktif):
adb install dist-android/SynapseLocal-debug.apk

# Atau kirim file APK ke HP dan install manual
# (Aktifkan "Install dari sumber tidak dikenal" di Pengaturan → Keamanan)
```

### Konfigurasi Backend untuk Android
Setelah APK terinstall, buka app → layar **"Connect to Backend"**:
- Jika backend di PC yang sama jaringan WiFi: masukkan IP PC, contoh `http://192.168.1.5:8000`
- Jika backend di HP yang sama (via Termux): gunakan `http://localhost:8000`
- Pastikan backend sudah jalan dulu: `./scripts/run.sh`

---

## MENJALANKAN BACKEND DI HP ANDROID (Termux)

```bash
# Install Termux dari F-Droid (bukan Play Store)
# Buka Termux:

pkg install python nodejs git
git clone <repo> synapse-local
cd synapse-local
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/run.sh

# Backend akan jalan di http://localhost:8000
# Di app Android → Server settings → http://localhost:8000
```

---

## STRUKTUR SETELAH BUILD

```
synapse-local/
├── dist-electron/          ← Desktop installers
│   ├── Synapse-Local-Setup-3.0.0.exe    (Windows)
│   ├── Synapse-Local-3.0.0.dmg          (macOS)
│   └── Synapse-Local-3.0.0.AppImage     (Linux)
├── dist-android/           ← Android APK
│   └── SynapseLocal-debug.apk
├── frontend/
│   └── android/            ← Android project (generated)
│       └── app/build/outputs/apk/
└── desktop/                ← Electron source
    └── node_modules/
```

---

## TROUBLESHOOTING

### Electron: "Python not found"
```bash
# Windows: install Python dari microsoft store atau python.org
# Pastikan Python ada di PATH
python --version
```

### Electron: "Backend tidak start"
```bash
# Cek log
cat ~/Library/Application\ Support/synapse-local/logs/backend.log   # macOS
cat ~/.config/synapse-local/logs/backend.log                        # Linux
cat %APPDATA%\synapse-local\logs\backend.log                        # Windows
```

### Android: "Cleartext traffic not permitted"
File `android/app/src/main/res/xml/network_security_config.xml` sudah dibuat otomatis oleh Capacitor dengan `android:usesCleartextTraffic="true"`.

### Android: Gradle build failed
```bash
# Pastikan ANDROID_HOME benar dan SDK terinstall
$ANDROID_HOME/platform-tools/adb version
# Coba:
cd frontend/android && ./gradlew clean assembleDebug
```

### Ollama tidak ditemukan saat Electron start
```bash
# Install Ollama dulu:
curl -fsSL https://ollama.com/install.sh | sh
# Kemudian pull model:
ollama pull llama3
ollama pull deepseek-coder
ollama pull nomic-embed-text
```
