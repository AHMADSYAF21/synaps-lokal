import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

export default function IntelligencePanel() {
  const [tab, setTab]       = useState('monitor')
  const [stats, setStats]   = useState(null)
  const [profile, setProfile] = useState(null)
  const [dimensions, setDimensions] = useState({})
  const [milestones, setMilestones] = useState([])
  const [growthData, setGrowthData] = useState([])
  const canvasRef = useRef(null)

  // Hypothesis state
  const [observation, setObservation] = useState('')
  const [hypOutput, setHypOutput]     = useState('')
  const [hypRunning, setHypRunning]   = useState(false)
  const [hypMode, setHypMode]         = useState('iterate')  // iterate|causal|abductive|argument|think
  const [causalInput, setCausalInput] = useState('')
  const [abductiveInputs, setAbductiveInputs] = useState('')
  const [argInput, setArgInput]       = useState('')
  const [thinkQ, setThinkQ]           = useState('')

  // Uncertainty state
  const [uncQ, setUncQ]           = useState('')
  const [uncResult, setUncResult] = useState(null)
  const [uncOutput, setUncOutput] = useState('')
  const [uncRunning, setUncRunning] = useState(false)
  const [socraticQ, setSocraticQ] = useState('')
  const [socResult, setSocResult] = useState(null)

  // Consolidation state
  const [consolHistory, setConsolHistory] = useState([])
  const [consolRunning, setConsolRunning] = useState(false)
  const [consolResult, setConsolResult]   = useState(null)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [st, pr, dim, ms, gr] = await Promise.all([
        apiClient.intelStats(),
        apiClient.intelProfile(7),
        apiClient.intelDimensions(),
        apiClient.intelMilestones(),
        apiClient.intelGrowth(14, 24),
      ])
      setStats(st)
      setProfile(pr)
      setDimensions(dim.dimensions || {})
      setMilestones(ms.milestones || [])
      setGrowthData(gr.chart || [])
      if (gr.chart?.length > 0) setTimeout(() => drawGrowth(gr.chart), 100)
    } catch(e) { console.error(e) }
    // Consolidation history
    try {
      const r = await apiClient.consolidationHistory(5)
      setConsolHistory(r.history || [])
    } catch {}
  }

  function drawGrowth(data) {
    const canvas = canvasRef.current
    if (!canvas || !data?.length) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = 160
    ctx.clearRect(0, 0, W, H)

    const scores = data.map(d => d.avg_score)
    const minS = Math.min(...scores) * 0.9
    const maxS = Math.max(...scores) * 1.05

    // Draw grid
    ctx.strokeStyle = '#1e2530'; ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = H - (i / 4) * H * 0.8 - H * 0.1
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
      ctx.fillStyle = '#3a4555'; ctx.font = '9px monospace'
      ctx.fillText(((minS + (i/4)*(maxS-minS))).toFixed(1), 4, y - 2)
    }

    // Draw line
    ctx.strokeStyle = '#00e5a0'; ctx.lineWidth = 2; ctx.beginPath()
    data.forEach((d, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * (W - 20) + 10
      const y = H - ((d.avg_score - minS) / (maxS - minS)) * H * 0.8 - H * 0.1
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Dots
    data.forEach((d, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * (W - 20) + 10
      const y = H - ((d.avg_score - minS) / (maxS - minS)) * H * 0.8 - H * 0.1
      ctx.beginPath(); ctx.arc(x, y, 3, 0, 2*Math.PI)
      ctx.fillStyle = '#00e5a0'; ctx.fill()
    })
  }

  async function runHypothesis() {
    if (!observation.trim() || hypRunning) return
    setHypRunning(true); setHypOutput('')
    apiClient.hypothesisStream(
      observation, 3,
      c => setHypOutput(p => p + c),
      () => setHypRunning(false),
      e => { setHypOutput(p => p + `\n[ERROR] ${e.message}`); setHypRunning(false) }
    )
  }

  async function runSpecialHyp() {
    setHypRunning(true); setHypOutput('')
    try {
      let r
      if (hypMode === 'causal') {
        r = await apiClient.causalAnalysis(causalInput)
        setHypOutput(JSON.stringify(r, null, 2))
      } else if (hypMode === 'abductive') {
        const obs = abductiveInputs.split('\n').filter(l => l.trim())
        r = await apiClient.abductiveInference(obs)
        setHypOutput(JSON.stringify(r, null, 2))
      } else if (hypMode === 'argument') {
        r = await apiClient.analyzeArgument(argInput)
        setHypOutput(JSON.stringify(r, null, 2))
      } else if (hypMode === 'think') {
        apiClient.thinkExplicitly(
          thinkQ, '',
          c => setHypOutput(p => p + c),
          () => setHypRunning(false),
          e => { setHypOutput(p => p + `\nERROR: ${e.message}`); setHypRunning(false) }
        )
        return
      }
    } catch(e) { setHypOutput(`Error: ${e.message}`) }
    setHypRunning(false)
  }

  async function runUncertainty() {
    if (!uncQ.trim() || uncRunning) return
    setUncRunning(true); setUncResult(null); setUncOutput('')
    try {
      const r = await apiClient.uncertaintyAssess(uncQ)
      setUncResult(r)
    } catch(e) { console.error(e) }
    setUncRunning(false)
  }

  async function runUncertaintyAnswer() {
    if (!uncQ.trim() || uncRunning) return
    setUncRunning(true); setUncOutput('')
    apiClient.uncertaintyAnswerStream(
      uncQ, '',
      c => setUncOutput(p => p + c),
      () => setUncRunning(false),
      e => { setUncOutput(p => p + `\nERROR: ${e.message}`); setUncRunning(false) }
    )
  }

  async function runSocratic() {
    if (!socraticQ.trim()) return
    const r = await apiClient.socraticCheck(socraticQ)
    setSocResult(r)
  }

  async function runConsolidation() {
    setConsolRunning(true); setConsolResult(null)
    try {
      const r = await apiClient.runConsolidation('default', false)
      setConsolResult(r)
      await loadAll()
    } catch(e) { setConsolResult({ error: e.message }) }
    setConsolRunning(false)
  }

  const trendColor = t => t === 'improving' ? '#10b981' : t === 'declining' ? '#ef4444' : '#f59e0b'
  const trendIcon  = t => t === 'improving' ? '↗' : t === 'declining' ? '↘' : '→'

  const dimColors = {
    reasoning:'#6366f1', knowledge:'#06b6d4', creativity:'#f59e0b',
    precision:'#10b981', adaptability:'#8b5cf6', meta_learning:'#ec4899',
    consistency:'#14b8a6', self_awareness:'#f97316',
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🧠 Intelligence</h2>
        <p className="panel-sub">Hypothesis testing · Uncertainty calibration · Memory consolidation · Growth tracking</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box">
            <span className="stat-n">{stats.avg_overall?.toFixed(1)||'—'}</span>
            <span>Avg Score</span>
          </div>
          <div className="stat-box">
            <span className="stat-n" style={{color:trendColor(stats['7_day_trend'])}}>
              {trendIcon(stats['7_day_trend'])} {stats['7_day_growth']||'—'}
            </span>
            <span>7d Growth</span>
          </div>
          <div className="stat-box">
            <span className="stat-n meta-green">{stats.milestones_achieved||0}</span>
            <span>Milestones</span>
          </div>
          <div className="stat-box">
            <span className="stat-n">{stats.total_evaluations||0}</span>
            <span>Evaluations</span>
          </div>
        </div>
      )}

      <div className="memory-tabs" style={{flexWrap:'wrap'}}>
        {['monitor','hypothesis','uncertainty','consolidation'].map(t=>(
          <button key={t} className={`mem-tab ${tab===t?'active':''}`} onClick={()=>setTab(t)}>
            {t==='monitor'?'📊 Monitor':t==='hypothesis'?'🔬 Hypothesis':t==='uncertainty'?'⚖️ Uncertainty':'🧹 Consolidation'}
          </button>
        ))}
      </div>

      <div className="panel-body">
        {/* ── INTELLIGENCE MONITOR ── */}
        {tab === 'monitor' && (
          <div>
            {/* Growth chart */}
            {growthData.length > 0 && (
              <div>
                <div className="section-title">Intelligence Growth (14 days)</div>
                <canvas ref={canvasRef}
                  style={{width:'100%',height:160,background:'var(--bg2)',borderRadius:8,display:'block',marginBottom:16}}/>
              </div>
            )}

            {/* Profile */}
            {profile && (
              <div>
                <div className="section-title">7-Day Profile</div>
                <div className="intel-profile">
                  <div className="intel-row">
                    <span>Overall</span>
                    <div className="intel-bar-wrap">
                      <div className="intel-bar" style={{width:`${(profile.avg_overall/10)*100}%`,background:'var(--accent)'}}/>
                    </div>
                    <span className="intel-score">{profile.avg_overall?.toFixed(1)}</span>
                  </div>
                  {Object.entries(profile.dimension_avgs||{}).map(([dim, val])=>(
                    <div key={dim} className="intel-row">
                      <span style={{color:dimColors[dim]||'#888'}}>{dim}</span>
                      <div className="intel-bar-wrap">
                        <div className="intel-bar" style={{width:`${(val/10)*100}%`,background:dimColors[dim]||'#888'}}/>
                      </div>
                      <span className="intel-score">{val?.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
                <div style={{display:'flex',gap:12,marginTop:8,fontFamily:'var(--font-mono)',fontSize:11}}>
                  <span style={{color:'#10b981'}}>💪 {profile.top_strength}</span>
                  <span style={{color:'#ef4444'}}>⚠ {profile.top_weakness}</span>
                  <span style={{color:trendColor(profile.trend)}}>{trendIcon(profile.trend)} {profile.trend}</span>
                </div>
              </div>
            )}

            {/* Milestones */}
            {milestones.length > 0 && (
              <div style={{marginTop:16}}>
                <div className="section-title">🏆 Milestones Achieved</div>
                <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                  {milestones.map(m=>(
                    <div key={m.id} className="milestone-badge">
                      <span>🏅</span>
                      <span>{m.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── HYPOTHESIS ENGINE ── */}
        {tab === 'hypothesis' && (
          <div>
            <div className="collab-modes" style={{marginBottom:12}}>
              {[
                ['iterate','🔬 Hypothesis Test','Generate + iterate to conclusion'],
                ['causal','⛓ Causal Analysis','Map cause-effect relationships'],
                ['abductive','💡 Abduction','Best explanation for observations'],
                ['argument','⚖️ Argument','Analyze argument structure'],
                ['think','🧵 Think Explicitly','Step-by-step with confidence'],
              ].map(([id,label,desc])=>(
                <button key={id} className={`collab-mode-btn ${hypMode===id?'active':''}`}
                  onClick={()=>setHypMode(id)}>
                  <span>{label}</span><span className="mode-desc">{desc}</span>
                </button>
              ))}
            </div>

            {hypMode === 'iterate' && (
              <div className="input-row">
                <input className="panel-input"
                  placeholder="Observation to hypothesize about…"
                  value={observation} onChange={e=>setObservation(e.target.value)}
                  onKeyDown={e=>e.key==='Enter'&&runHypothesis()}/>
                <button className="btn-run" onClick={runHypothesis}
                  disabled={hypRunning||!observation.trim()}>
                  {hypRunning?<span className="spinner-sm"/>:'🔬 Run'}
                </button>
              </div>
            )}
            {hypMode === 'causal' && (
              <div className="input-row">
                <input className="panel-input" placeholder="Describe a situation to analyse causally…"
                  value={causalInput} onChange={e=>setCausalInput(e.target.value)}/>
                <button className="btn-run" onClick={runSpecialHyp} disabled={hypRunning}>{hypRunning?<span className="spinner-sm"/>:'Analyse'}</button>
              </div>
            )}
            {hypMode === 'abductive' && (
              <div>
                <textarea className="panel-textarea" rows={4}
                  placeholder="List observations (one per line)…"
                  value={abductiveInputs} onChange={e=>setAbductiveInputs(e.target.value)}/>
                <button className="btn-run" onClick={runSpecialHyp} disabled={hypRunning} style={{marginTop:6}}>{hypRunning?<span className="spinner-sm"/>:'Infer Best Explanation'}</button>
              </div>
            )}
            {hypMode === 'argument' && (
              <div>
                <textarea className="panel-textarea" rows={4}
                  placeholder="Paste the argument to analyze…"
                  value={argInput} onChange={e=>setArgInput(e.target.value)}/>
                <button className="btn-run" onClick={runSpecialHyp} disabled={hypRunning} style={{marginTop:6}}>{hypRunning?<span className="spinner-sm"/>:'Analyze'}</button>
              </div>
            )}
            {hypMode === 'think' && (
              <div className="input-row">
                <input className="panel-input"
                  placeholder="Question to reason about step by step…"
                  value={thinkQ} onChange={e=>setThinkQ(e.target.value)}
                  onKeyDown={e=>e.key==='Enter'&&runSpecialHyp()}/>
                <button className="btn-run" onClick={runSpecialHyp} disabled={hypRunning}>{hypRunning?<span className="spinner-sm"/>:'Think'}</button>
              </div>
            )}

            {hypOutput && (
              <div className="output-block" style={{maxHeight:500,overflowY:'auto',marginTop:12}}>
                <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.8}}>
                  {hypOutput}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* ── UNCERTAINTY ENGINE ── */}
        {tab === 'uncertainty' && (
          <div>
            <div className="form-field">
              <label className="form-label">Question to assess</label>
              <div className="input-row">
                <input className="panel-input"
                  placeholder="Ask anything — see confidence + knowledge boundaries"
                  value={uncQ} onChange={e=>setUncQ(e.target.value)}
                  onKeyDown={e=>e.key==='Enter'&&runUncertainty()}/>
                <button className="btn-sm" onClick={runUncertainty} disabled={uncRunning}>
                  {uncRunning?<span className="spinner-sm"/>:'Assess'}
                </button>
                <button className="btn-run" onClick={runUncertaintyAnswer} disabled={uncRunning}>
                  {uncRunning?<span className="spinner-sm"/>:'Answer'}
                </button>
              </div>
            </div>

            {uncResult && (
              <div className="result-card">
                <div className="result-header">
                  <span>Confidence: <b>{(uncResult.confidence*100).toFixed(0)}%</b> · {uncResult.confidence_label}</span>
                  <span className={`mem-tag ${uncResult.hallucination_risk === 'high' ? 'skill-badge' : ''}`}
                    style={{color: uncResult.hallucination_risk==='high'?'var(--red)':'var(--text-muted)'}}>
                    hallucination: {uncResult.hallucination_risk}
                  </span>
                </div>
                <div className="intel-row" style={{marginTop:8}}>
                  <span style={{fontSize:11,color:'var(--text-dim)'}}>Epistemic uncertainty</span>
                  <div className="intel-bar-wrap">
                    <div className="intel-bar" style={{width:`${uncResult.epistemic_uncertainty*100}%`,background:'#6366f1'}}/>
                  </div>
                  <span className="intel-score">{(uncResult.epistemic_uncertainty*100).toFixed(0)}%</span>
                </div>
                {uncResult.knowledge_gaps?.length > 0 && (
                  <div>
                    <div className="form-label" style={{marginTop:8}}>Knowledge gaps:</div>
                    {uncResult.knowledge_gaps.slice(0,3).map((g,i)=><div key={i} className="task-desc">• {g}</div>)}
                  </div>
                )}
                {uncResult.caveat && <div className="distill-card" style={{marginTop:8,padding:8}}><em>{uncResult.caveat}</em></div>}
              </div>
            )}

            {uncOutput && (
              <div className="output-block" style={{maxHeight:400,overflowY:'auto',marginTop:12}}>
                <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.8}}>
                  {uncOutput}
                </pre>
              </div>
            )}

            <div className="section-title" style={{marginTop:16}}>Socratic Clarification Check</div>
            <div className="input-row">
              <input className="panel-input"
                placeholder="Paste a request — check if clarification is needed"
                value={socraticQ} onChange={e=>setSocraticQ(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&runSocratic()}/>
              <button className="btn-sm" onClick={runSocratic}>Check</button>
            </div>
            {socResult && (
              <div className="result-card" style={{marginTop:8}}>
                <div className="result-header">
                  <span>Clarity: <b>{(socResult.clarity_score*100).toFixed(0)}%</b></span>
                  <span className="mem-tag">{socResult.needs_clarification?'❓ Needs clarification':'✅ Clear'}</span>
                </div>
                {(socResult.questions||[]).slice(0,3).map((q,i)=>(
                  <div key={i} className="task-item" style={{marginTop:6}}>
                    <span className="mem-tag">{q.priority}</span>
                    <span className="task-title">{q.question}</span>
                    <span className="task-desc">{q.why_needed}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── MEMORY CONSOLIDATION ── */}
        {tab === 'consolidation' && (
          <div>
            <p className="panel-hint">
              Consolidation compresses redundant memories, merges similar ones, promotes important ones to long-term knowledge,
              and builds episodic summaries. Runs automatically every {'{Config.CONSOLIDATION_INTERVAL_H}'} hours.
            </p>
            <button className="btn-run" onClick={runConsolidation} disabled={consolRunning}>
              {consolRunning?<><span className="spinner-sm"/> Consolidating…</>:'🧹 Run Consolidation Now'}
            </button>

            {consolResult && (
              <div className="result-card success" style={{marginTop:12}}>
                <div className="result-header">✅ Consolidation Complete</div>
                <div className="bench-runs">
                  {[
                    ['Memories before', consolResult.memories_before],
                    ['Memories after',  consolResult.memories_after],
                    ['Merged',          consolResult.merged],
                    ['Forgotten',       consolResult.forgotten],
                    ['Promoted to knowledge', consolResult.promoted],
                    ['Episodes created', consolResult.episodes_created],
                    ['Duration',        `${consolResult.duration_s}s`],
                  ].map(([k,v])=>(
                    <div key={k} className="bench-run-item">
                      <span className="bench-run-suite">{k}</span>
                      <span className="bench-run-score">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {consolHistory.length > 0 && (
              <div style={{marginTop:16}}>
                <div className="section-title">Recent Consolidation History</div>
                {consolHistory.map((h,i)=>(
                  <div key={i} className="bench-run-item">
                    <span className="bench-run-suite">{h.session_id}</span>
                    <span className="bench-run-model">
                      -{h.forgotten} forgotten, ×{h.merged} merged, ↑{h.promoted} promoted
                    </span>
                    <span className="bench-run-date">
                      {new Date(h.timestamp*1000).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
