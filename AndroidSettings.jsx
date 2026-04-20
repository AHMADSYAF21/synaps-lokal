// src/components/AndroidSettings.jsx
// Shows on Android when backend is not reachable — lets user set server URL
import { useState, useEffect } from 'react'
import { apiClient, setBackendUrl, getBackendUrl } from '../api/client'

export default function AndroidSettings({ onConnected }) {
  const [url, setUrl]         = useState(getBackendUrl())
  const [testing, setTesting] = useState(false)
  const [result, setResult]   = useState(null)

  const commonUrls = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://10.0.2.2:8000',      // Android emulator → host
    'http://192.168.1.100:8000',
    'http://192.168.0.100:8000',
  ]

  async function testConnection(testUrl) {
    setTesting(true)
    setResult(null)
    const target = testUrl || url
    setBackendUrl(target)
    try {
      const data = await apiClient.health()
      setResult({ ok: true, msg: `✅ Connected! Ollama: ${data.ollama ? 'online' : 'offline'}` })
      if (data.ollama !== false) onConnected?.(target)
    } catch (e) {
      setResult({ ok: false, msg: `❌ ${e.message}` })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="android-settings">
      <div className="as-header">
        <div className="as-icon">◈</div>
        <h2>Connect to Backend</h2>
        <p>Enter the IP address of the machine running<br/>
           the Synapse backend server</p>
      </div>

      <div className="as-body">
        <label className="form-label">Backend URL</label>
        <div className="as-input-row">
          <input
            className="panel-input"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="http://192.168.1.x:8000"
            onKeyDown={e => e.key === 'Enter' && testConnection()}
          />
          <button className="btn-run" onClick={() => testConnection()} disabled={testing}>
            {testing ? <span className="spinner-sm"/> : 'Test'}
          </button>
        </div>

        {result && (
          <div className={`as-result ${result.ok ? 'ok' : 'err'}`}>
            {result.msg}
          </div>
        )}

        <div className="as-divider">Quick connect</div>
        <div className="as-presets">
          {commonUrls.map(u => (
            <button key={u} className="as-preset"
              onClick={() => { setUrl(u); testConnection(u) }}>
              {u}
            </button>
          ))}
        </div>

        <div className="as-help">
          <b>How to start the backend:</b>
          <ol>
            <li>On a PC: run <code>./scripts/run.sh</code></li>
            <li>On Termux (same phone): run <code>./scripts/run.sh</code></li>
            <li>Enter the IP shown in the terminal</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
