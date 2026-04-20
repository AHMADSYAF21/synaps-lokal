/**
 * Electron Preload — IPC Bridge
 * Exposes safe APIs from main process to renderer
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('synapse', {
  getBackendUrl:   () => ipcRenderer.invoke('get-backend-url'),
  getDataDir:      () => ipcRenderer.invoke('get-data-dir'),
  getLogDir:       () => ipcRenderer.invoke('get-log-dir'),
  pingBackend:     () => ipcRenderer.invoke('ping-backend'),
  restartBackend:  () => ipcRenderer.invoke('restart-backend'),
  openDataFolder:  () => ipcRenderer.invoke('open-data-folder'),
  openLogFolder:   () => ipcRenderer.invoke('open-log-folder'),
  openBrowser:     () => ipcRenderer.invoke('open-browser'),
  isElectron:      true,
  platform:        process.platform,

  // Listen to splash status events
  onStatus: (callback) => {
    ipcRenderer.on('status', (_event, data) => callback(data))
    return () => ipcRenderer.removeAllListeners('status')
  },
})
