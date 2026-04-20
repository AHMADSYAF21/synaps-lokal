import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

export default function KnowledgeGraphPanel() {
  const [stats, setStats]     = useState(null)
  const [entities, setEntities] = useState([])
  const [query, setQuery]     = useState('')
  const [answer, setAnswer]   = useState('')
  const [search, setSearch]   = useState('')
  const [extractText, setExtractText] = useState('')
  const [tab, setTab]         = useState('query')
  const [loading, setLoading] = useState(false)
  const [vizData, setVizData] = useState(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    loadStats()
    loadViz()
  }, [])

  async function loadStats() {
    try {
      const r = await apiClient.kgStats()
      setStats(r)
    } catch(e) {}
  }

  async function loadViz() {
    try {
      const r = await apiClient.kgViz(80)
      setVizData(r)
      if (r.nodes?.length > 0) drawGraph(r)
    } catch(e) {}
  }

  async function handleQuery() {
    if (!query.trim() || loading) return
    setLoading(true); setAnswer('')
    try {
      const r = await apiClient.kgQuery(query)
      setAnswer(r.answer)
      setEntities(r.entities || [])
    } catch(e) { setAnswer(`Error: ${e.message}`) }
    finally { setLoading(false) }
  }

  async function handleSearch() {
    if (!search.trim() || loading) return
    setLoading(true)
    try {
      const r = await apiClient.kgSearch(search)
      setEntities(r.entities || [])
    } catch(e) {}
    finally { setLoading(false) }
  }

  async function handleExtract() {
    if (!extractText.trim() || loading) return
    setLoading(true)
    try {
      const r = await apiClient.kgExtract(extractText)
      if (r.success) {
        alert(`✅ Extracted: ${r.entities_added} entities, ${r.relations_added} relations`)
        await loadStats()
        await loadViz()
      } else {
        alert(`Error: ${r.error}`)
      }
    } catch(e) { alert(e.message) }
    finally { setLoading(false) }
  }

  // Simple canvas graph renderer
  function drawGraph(data) {
    const canvas = canvasRef.current
    if (!canvas || !data?.nodes?.length) return
    const ctx  = canvas.getContext('2d')
    const W    = canvas.width  = canvas.offsetWidth
    const H    = canvas.height = 300
    ctx.clearRect(0, 0, W, H)

    const typeColors = {
      person:'#f59e0b', org:'#6366f1', concept:'#10b981',
      tech:'#06b6d4', place:'#ef4444', event:'#8b5cf6', other:'#888',
    }

    // Position nodes in circle
    const nodes = data.nodes.slice(0, 30)
    const cx = W/2, cy = H/2, r = Math.min(W, H) * 0.38
    const positions = nodes.map((n, i) => ({
      ...n,
      x: cx + r * Math.cos((2*Math.PI*i)/nodes.length),
      y: cy + r * Math.sin((2*Math.PI*i)/nodes.length),
    }))
    const posMap = Object.fromEntries(positions.map(p => [p.id, p]))

    // Draw edges
    ctx.strokeStyle = '#1e2530'
    ctx.lineWidth = 1
    for (const link of (data.links||[]).slice(0,50)) {
      const s = posMap[link.source], t = posMap[link.target]
      if (!s || !t) continue
      ctx.beginPath()
      ctx.moveTo(s.x, s.y)
      ctx.lineTo(t.x, t.y)
      ctx.stroke()
    }

    // Draw nodes
    for (const n of positions) {
      const color = typeColors[n.type] || '#888'
      ctx.beginPath()
      ctx.arc(n.x, n.y, 6, 0, 2*Math.PI)
      ctx.fillStyle = color
      ctx.fill()
      ctx.font = '9px monospace'
      ctx.fillStyle = '#c8d4e0'
      ctx.textAlign = 'center'
      ctx.fillText(n.name.slice(0,12), n.x, n.y-10)
    }
  }

  const typeColors = {
    person:'#f59e0b', org:'#6366f1', concept:'#10b981',
    tech:'#06b6d4', place:'#ef4444', event:'#8b5cf6', other:'#888',
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🕸 Knowledge Graph</h2>
        <p className="panel-sub">Extract entities & relations, query structured knowledge</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.entities}</span><span>Entities</span></div>
          <div className="stat-box"><span className="stat-n">{stats.relations}</span><span>Relations</span></div>
          {Object.entries(stats.by_type||{}).slice(0,3).map(([t,c])=>(
            <div key={t} className="stat-box">
              <span className="stat-n" style={{color:typeColors[t]||'#888'}}>{c}</span>
              <span>{t}</span>
            </div>
          ))}
        </div>
      )}

      <div className="memory-tabs">
        {['query','search','extract','graph'].map(t => (
          <button key={t} className={`mem-tab ${tab===t?'active':''}`} onClick={()=>setTab(t)}>
            {t==='query'?'🔍 Query':t==='search'?'🔎 Entities':t==='extract'?'⬆ Extract':'🕸 Visualise'}
          </button>
        ))}
      </div>

      <div className="panel-body">
        {tab === 'query' && (
          <div>
            <div className="input-row">
              <input className="panel-input"
                placeholder="Ask something about your knowledge graph…"
                value={query} onChange={e=>setQuery(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&handleQuery()}/>
              <button className="btn-run" onClick={handleQuery} disabled={loading||!query.trim()}>
                {loading?<span className="spinner-sm"/>:'Ask'}
              </button>
            </div>
            {answer && (
              <div className="output-block">
                <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.7}}>
                  {answer}
                </pre>
              </div>
            )}
            {entities.length > 0 && (
              <div>
                <div className="section-title">Entities used</div>
                <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                  {entities.map(e=>(
                    <span key={e.id} className="mem-tag"
                      style={{borderColor:typeColors[e.type]||'#888'}}>
                      {e.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'search' && (
          <div>
            <div className="input-row">
              <input className="panel-input" placeholder="Search entities…"
                value={search} onChange={e=>setSearch(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&handleSearch()}/>
              <button className="btn-run" onClick={handleSearch} disabled={loading}>
                {loading?<span className="spinner-sm"/>:'Search'}
              </button>
            </div>
            {entities.length > 0 && (
              <div className="skill-list">
                {entities.map(e=>(
                  <div key={e.id} className="skill-card">
                    <div className="skill-header">
                      <span className="skill-type-dot" style={{background:typeColors[e.type]||'#888'}}/>
                      <span className="skill-name">{e.name}</span>
                      <span className="mem-tag">{e.type}</span>
                    </div>
                    {e.description && <p className="skill-desc">{e.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'extract' && (
          <div>
            <p className="panel-hint">Paste any text — AI extracts entities and relationships</p>
            <textarea className="panel-textarea" rows={6}
              placeholder="Paste text here to extract knowledge…"
              value={extractText} onChange={e=>setExtractText(e.target.value)}/>
            <button className="btn-run" onClick={handleExtract}
              disabled={loading||!extractText.trim()}>
              {loading?<><span className="spinner-sm"/> Extracting…</>:'⬆ Extract Knowledge'}
            </button>
          </div>
        )}

        {tab === 'graph' && (
          <div>
            <div className="section-title">Graph Visualisation ({vizData?.nodes?.length||0} nodes)</div>
            <canvas ref={canvasRef}
              style={{width:'100%',height:300,background:'var(--bg2)',borderRadius:8,display:'block'}}/>
            <p className="panel-hint">Entity types: {
              Object.keys(typeColors).map(t=>(
                <span key={t} style={{color:typeColors[t],marginRight:8}}>{t}</span>
              ))
            }</p>
          </div>
        )}
      </div>
    </div>
  )
}
