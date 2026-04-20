import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function PluginsPanel() {
  const [plugins, setPlugins]   = useState([])
  const [stats, setStats]       = useState(null)
  const [allowed, setAllowed]   = useState([])
  const [pkg, setPkg]           = useState('')
  const [desc, setDesc]         = useState('')
  const [installing, setInstalling] = useState(false)
  const [result, setResult]     = useState(null)
  const [filter, setFilter]     = useState('')
  const [tab, setTab]           = useState('installed')

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [p, a] = await Promise.all([
        apiClient.listPlugins(),
        apiClient.allowedPlugins(),
      ])
      setPlugins(p.plugins || [])
      setStats(p.stats)
      setAllowed(a.packages || [])
    } catch(e) { console.error(e) }
  }

  async function handleInstall() {
    if (!pkg.trim() || installing) return
    setInstalling(true); setResult(null)
    try {
      const r = await apiClient.installPlugin(pkg, desc, true)
      setResult(r)
      if (r.success) {
        await loadAll()
        setPkg(''); setDesc('')
      }
    } catch(e) { setResult({ success:false, error:e.message }) }
    finally { setInstalling(false) }
  }

  async function handleRemove(pkg) {
    if (!confirm(`Remove plugin '${pkg}'?`)) return
    await apiClient.removePlugin(pkg)
    setPlugins(p => p.filter(x => x.package !== pkg))
  }

  const filteredAllowed = filter
    ? allowed.filter(p => p.toLowerCase().includes(filter.toLowerCase()))
    : allowed

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🔌 Plugin System</h2>
        <p className="panel-sub">Install Python packages — AI auto-generates tool wrappers</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total_plugins}</span><span>Installed</span></div>
          <div className="stat-box"><span className="stat-n meta-green">{stats.total_tools}</span><span>Tools Added</span></div>
          <div className="stat-box"><span className="stat-n">{stats.allowed_packages}</span><span>Available</span></div>
        </div>
      )}

      <div className="memory-tabs">
        <button className={`mem-tab ${tab==='installed'?'active':''}`} onClick={()=>setTab('installed')}>
          🔌 Installed ({plugins.length})
        </button>
        <button className={`mem-tab ${tab==='install'?'active':''}`} onClick={()=>setTab('install')}>
          ＋ Install
        </button>
        <button className={`mem-tab ${tab==='catalog'?'active':''}`} onClick={()=>setTab('catalog')}>
          📦 Catalog
        </button>
      </div>

      <div className="panel-body">
        {/* INSTALLED */}
        {tab === 'installed' && (
          plugins.length === 0
            ? <div className="memory-empty">No plugins installed yet</div>
            : (
              <div className="skill-list">
                {plugins.map(p => (
                  <div key={p.plugin_id} className="skill-card">
                    <div className="skill-header">
                      <span>🔌</span>
                      <span className="skill-name">{p.name}</span>
                      <span className="mem-tag">v{p.version}</span>
                      <span className="skill-uses">{p.tool_count} tools</span>
                      <button className="del-btn" onClick={()=>handleRemove(p.package)}>✕</button>
                    </div>
                    <p className="skill-desc">{p.description}</p>
                    {p.capabilities?.length > 0 && (
                      <div className="skill-tags">
                        {p.capabilities.map(c=><span key={c} className="mem-tag">⚙ {c}</span>)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
        )}

        {/* INSTALL */}
        {tab === 'install' && (
          <div>
            <p className="panel-hint">
              Install any package from the allowed catalog. AI will auto-generate tool wrappers.
            </p>
            <div className="form-field">
              <label className="form-label">Package name</label>
              <input className="panel-input" placeholder="e.g. numpy, pandas, pillow"
                value={pkg} onChange={e=>setPkg(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&handleInstall()}/>
            </div>
            <div className="form-field">
              <label className="form-label">Description (helps AI generate better tools)</label>
              <input className="panel-input" placeholder="e.g. 'numerical computing library'"
                value={desc} onChange={e=>setDesc(e.target.value)}/>
            </div>
            <button className="btn-run" onClick={handleInstall}
              disabled={installing||!pkg.trim()}>
              {installing?<><span className="spinner-sm"/> Installing…</>:'🔌 Install Plugin'}
            </button>

            {result && (
              <div className={`result-card ${result.success?'success':'warn'}`} style={{marginTop:12}}>
                <div className="result-header">
                  <span>{result.success?'✅':' ❌'} {result.message||result.error}</span>
                </div>
                {result.success && (
                  <div>
                    <div className="mem-tag">v{result.version}</div>
                    {result.tools_added?.length > 0 && (
                      <div className="skill-tags" style={{marginTop:6}}>
                        {result.tools_added.map(t=><span key={t.name} className="mem-tag">⚙ {t.name}</span>)}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* CATALOG */}
        {tab === 'catalog' && (
          <div>
            <input className="panel-input" placeholder="Filter packages…"
              value={filter} onChange={e=>setFilter(e.target.value)}
              style={{marginBottom:10}}/>
            <div className="plugin-catalog">
              {filteredAllowed.map(p => {
                const isInstalled = plugins.some(x => x.package === p)
                return (
                  <div key={p} className="catalog-item">
                    <span className="catalog-name">{p}</span>
                    {isInstalled
                      ? <span className="mem-tag" style={{color:'var(--accent)'}}>✓ installed</span>
                      : <button className="btn-sm" style={{fontSize:10,padding:'2px 8px'}}
                          onClick={()=>{setPkg(p);setTab('install')}}>+ Add</button>
                    }
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
