/**
 * SYNAPSE LOCAL — Electron Main Process
 * Manages: splash screen, backend startup, main window, tray, IPC
 */

const {
  app, BrowserWindow, ipcMain, Tray, Menu, nativeImage,
  dialog, shell, Notification
} = require('electron')
const { spawn, exec }  = require('child_process')
const path  = require('path')
const fs    = require('fs')
const http  = require('http')
const os    = require('os')

// ── Paths ─────────────────────────────────────────────────────────────────
const IS_PACKAGED  = app.isPackaged
const ROOT_DIR     = IS_PACKAGED
  ? path.join(process.resourcesPath, 'app')
  : path.join(__dirname, '..')
const BACKEND_DIR  = path.join(ROOT_DIR, 'backend')
const FRONTEND_DIST= path.join(ROOT_DIR, 'frontend', 'dist')
const DATA_DIR     = path.join(app.getPath('userData'), 'data')
const VENV_DIR     = path.join(app.getPath('userData'), 'venv')
const LOG_DIR      = path.join(app.getPath('userData'), 'logs')

// Ensure dirs exist
;[DATA_DIR, LOG_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }))

const BACKEND_PORT  = 8000
const BACKEND_URL   = `http://127.0.0.1:${BACKEND_PORT}`

// ── State ─────────────────────────────────────────────────────────────────
let splashWin   = null
let mainWin     = null
let tray        = null
let backendProc = null
let ollamaProc  = null
let isQuitting  = false

// ── Logging ───────────────────────────────────────────────────────────────
const logFile = fs.createWriteStream(
  path.join(LOG_DIR, 'electron.log'), { flags: 'a' }
)
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`
  console.log(line)
  logFile.write(line + '\n')
}

// ── Splash Window ─────────────────────────────────────────────────────────
function createSplash() {
  splashWin = new BrowserWindow({
    width: 480, height: 300,
    frame: false, transparent: true,
    alwaysOnTop: true, center: true,
    resizable: false, skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  })
  splashWin.loadFile(path.join(__dirname, 'splash.html'))
  splashWin.once('ready-to-show', () => splashWin.show())
}

function setSplashStatus(msg, progress = null) {
  log(`Splash: ${msg}`)
  if (splashWin && !splashWin.isDestroyed()) {
    splashWin.webContents.send('status', { msg, progress })
  }
}

// ── Main Window ───────────────────────────────────────────────────────────
function createMainWindow() {
  mainWin = new BrowserWindow({
    width: 1280, height: 800,
    minWidth: 800, minHeight: 550,
    show: false,
    title: 'Synapse Local',
    backgroundColor: '#0a0c0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      webSecurity: false,   // allow local API calls
    },
  })

  mainWin.loadFile(path.join(FRONTEND_DIST, 'index.html'))

  mainWin.once('ready-to-show', () => {
    if (splashWin && !splashWin.isDestroyed()) {
      splashWin.close()
      splashWin = null
    }
    mainWin.show()
    mainWin.focus()
    log('Main window shown')
  })

  mainWin.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWin.hide()
    }
  })

  mainWin.on('closed', () => { mainWin = null })

  // Build app menu
  const menu = Menu.buildFromTemplate([
    {
      label: 'Synapse',
      submenu: [
        { label: 'About', click: () => dialog.showMessageBox(mainWin, {
            title: 'Synapse Local', message: 'Synapse Local v3\nAutonomous AI — 100% Offline',
            detail: `Backend: ${BACKEND_URL}\nData: ${DATA_DIR}`,
          })
        },
        { type: 'separator' },
        { label: 'Open Data Folder', click: () => shell.openPath(DATA_DIR) },
        { label: 'Open Log Folder',  click: () => shell.openPath(LOG_DIR)  },
        { type: 'separator' },
        { label: 'Quit', accelerator: 'CmdOrCtrl+Q',
          click: () => { isQuitting = true; app.quit() }
        },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
  ])
  Menu.setApplicationMenu(menu)
}

// ── System Tray ───────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png')
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()

  tray = new Tray(icon)
  tray.setToolTip('Synapse Local — AI Running')

  const ctxMenu = Menu.buildFromTemplate([
    { label: '◈ Synapse Local', enabled: false },
    { type: 'separator' },
    { label: 'Show Window',  click: () => { mainWin?.show(); mainWin?.focus() } },
    { label: 'Open in Browser', click: () => shell.openExternal(`${BACKEND_URL}`) },
    { type: 'separator' },
    { label: 'Restart Backend', click: () => restartBackend() },
    { type: 'separator' },
    { label: 'Quit', click: () => { isQuitting = true; app.quit() } },
  ])
  tray.setContextMenu(ctxMenu)
  tray.on('double-click', () => { mainWin?.show(); mainWin?.focus() })
}

// ── Python / venv Setup ───────────────────────────────────────────────────
function getPythonCmd() {
  if (process.platform === 'win32') {
    const venvPy = path.join(VENV_DIR, 'Scripts', 'python.exe')
    if (fs.existsSync(venvPy)) return venvPy
    return 'python'
  }
  const venvPy = path.join(VENV_DIR, 'bin', 'python3')
  if (fs.existsSync(venvPy)) return venvPy
  return 'python3'
}

function runCmd(cmd, cwd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { cwd }, (err, stdout, stderr) => {
      if (err) reject(new Error(stderr || err.message))
      else resolve(stdout)
    })
  })
}

async function ensurePythonEnv() {
  setSplashStatus('Checking Python environment…', 20)
  const py = getPythonCmd()

  // Create venv if not exists
  if (!fs.existsSync(VENV_DIR)) {
    setSplashStatus('Creating Python virtual environment…', 25)
    try {
      await runCmd(`python3 -m venv "${VENV_DIR}"`, BACKEND_DIR)
    } catch {
      await runCmd(`python -m venv "${VENV_DIR}"`, BACKEND_DIR)
    }
  }

  // Install requirements
  setSplashStatus('Installing Python dependencies…', 30)
  const pip = process.platform === 'win32'
    ? path.join(VENV_DIR, 'Scripts', 'pip.exe')
    : path.join(VENV_DIR, 'bin', 'pip')
  const req = path.join(BACKEND_DIR, 'requirements.txt')
  await runCmd(`"${pip}" install -q -r "${req}"`, BACKEND_DIR)
}

// ── Ollama ────────────────────────────────────────────────────────────────
async function startOllama() {
  setSplashStatus('Starting Ollama…', 45)
  // Check if already running
  try {
    await pingUrl('http://127.0.0.1:11434/api/tags', 1000)
    log('Ollama already running')
    return
  } catch {}

  const ollamaLog = fs.createWriteStream(
    path.join(LOG_DIR, 'ollama.log'), { flags: 'a' }
  )
  ollamaProc = spawn('ollama', ['serve'], {
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  ollamaProc.stdout.pipe(ollamaLog)
  ollamaProc.stderr.pipe(ollamaLog)
  ollamaProc.on('error', (e) => log(`Ollama error: ${e.message}`))

  // Wait up to 10 seconds for Ollama
  for (let i = 0; i < 20; i++) {
    try {
      await pingUrl('http://127.0.0.1:11434/api/tags', 500)
      log('Ollama started')
      return
    } catch {}
    await sleep(500)
  }
  log('Ollama did not start in time — continuing anyway')
}

// ── Python Backend ────────────────────────────────────────────────────────
async function startBackend() {
  setSplashStatus('Starting AI backend…', 60)

  const py = getPythonCmd()
  const env = {
    ...process.env,
    CHROMA_PATH:        path.join(DATA_DIR, 'chroma'),
    SKILL_DB_PATH:      path.join(DATA_DIR, 'skills.db'),
    CAPABILITIES_DIR:   path.join(DATA_DIR, 'capabilities'),
    EVOLUTION_LOG_PATH: path.join(DATA_DIR, 'evolution.jsonl'),
    HOST: '127.0.0.1',
    PORT: String(BACKEND_PORT),
    PYTHONUNBUFFERED: '1',
  }
  // Windows: ensure data subdirs
  ;[env.CHROMA_PATH, env.CAPABILITIES_DIR].forEach(d =>
    fs.mkdirSync(d, { recursive: true })
  )

  const backendLog = fs.createWriteStream(
    path.join(LOG_DIR, 'backend.log'), { flags: 'a' }
  )

  backendProc = spawn(
    py,
    ['-m', 'uvicorn', 'main:app',
     '--host', '127.0.0.1',
     '--port', String(BACKEND_PORT),
     '--log-level', 'warning'],
    { cwd: BACKEND_DIR, env, stdio: ['ignore', 'pipe', 'pipe'] }
  )
  backendProc.stdout.pipe(backendLog)
  backendProc.stderr.pipe(backendLog)
  backendProc.on('error', (e) => {
    log(`Backend error: ${e.message}`)
    showBackendError(e.message)
  })
  backendProc.on('exit', (code) => {
    if (!isQuitting) {
      log(`Backend exited with code ${code}`)
    }
  })

  // Wait for backend ready (up to 30 seconds)
  setSplashStatus('Waiting for backend to be ready…', 70)
  for (let i = 0; i < 60; i++) {
    try {
      await pingUrl(`${BACKEND_URL}/health`, 500)
      log(`Backend ready at ${BACKEND_URL}`)
      return
    } catch {}
    await sleep(500)
  }
  throw new Error('Backend did not start within 30 seconds')
}

async function restartBackend() {
  log('Restarting backend…')
  if (backendProc) { backendProc.kill(); backendProc = null }
  await startBackend()
  mainWin?.webContents.reload()
}

// ── Helpers ───────────────────────────────────────────────────────────────
function pingUrl(url, timeout = 2000) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, { timeout }, (res) => {
      res.resume(); resolve(res.statusCode)
    })
    req.on('error', reject)
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')) })
  })
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms))

function showBackendError(msg) {
  dialog.showErrorBox('Backend Error',
    `Synapse backend failed to start:\n\n${msg}\n\n` +
    `Check logs at: ${LOG_DIR}`
  )
}

// ── IPC Handlers ──────────────────────────────────────────────────────────
ipcMain.handle('get-backend-url',  () => BACKEND_URL)
ipcMain.handle('get-data-dir',     () => DATA_DIR)
ipcMain.handle('get-log-dir',      () => LOG_DIR)
ipcMain.handle('ping-backend',     async () => {
  try { await pingUrl(`${BACKEND_URL}/health`); return true }
  catch { return false }
})
ipcMain.handle('restart-backend',  () => restartBackend())
ipcMain.handle('open-data-folder', () => shell.openPath(DATA_DIR))
ipcMain.handle('open-log-folder',  () => shell.openPath(LOG_DIR))
ipcMain.handle('open-browser',     () => shell.openExternal(BACKEND_URL))

// ── App Lifecycle ─────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  log(`=== Synapse Local starting (${process.platform}) ===`)
  createSplash()

  try {
    setSplashStatus('Initializing…', 10)
    await sleep(500)

    await ensurePythonEnv()
    await startOllama()
    await startBackend()

    setSplashStatus('Loading interface…', 90)
    createMainWindow()
    createTray()

    setSplashStatus('Ready!', 100)
    await sleep(400)

    new Notification({
      title: 'Synapse Local',
      body: 'AI is ready — running fully offline',
    }).show()

  } catch (err) {
    log(`Startup error: ${err}`)
    setSplashStatus(`Error: ${err.message}`, null)
    await sleep(2000)
    dialog.showErrorBox('Startup Failed', err.message)
    app.quit()
  }
})

app.on('window-all-closed', () => {
  // Keep running in tray (don't quit)
  if (process.platform !== 'darwin') {
    // do nothing — tray keeps app alive
  }
})

app.on('activate', () => {
  if (!mainWin) createMainWindow()
  else { mainWin.show(); mainWin.focus() }
})

app.on('before-quit', () => {
  isQuitting = true
  log('Shutting down…')
  if (backendProc) { backendProc.kill('SIGTERM'); backendProc = null }
  if (ollamaProc)  { ollamaProc.kill('SIGTERM');  ollamaProc  = null }
})
