import { useState, useEffect } from "react"
import { apiClient } from "../api/client"

export default function SystemPanel({ health }) {
  const [healStatus, setHealStatus] = useState(null)
  const [repairLog, setRepairLog] = useState([])
  const [loading, setLoading] = useState(false)
  const [reasonTest, setReasonTest] = useState({ task:"", strategy:"auto", result:null, running:false })

  useEffect(() => { loadHealing() }, [])

  async function loadHealing() {
    try {
      const [s, l] = await Promise.all([apiClient.healingStatus(), apiClient.healingLog()])
      setHealStatus(s)
      setRepairLog(l.repairs || [])
    } catch(e) {}
  }

  async function forceRepair(component) {
    setLoading(true)
    await apiClient.forceRepair(component)
    await loadHealing()
    setLoading(false)
  }

  async function runReason() {
    if (!reasonTest.task.trim()) return
    setReasonTest(s => ({...s, running:true, result:null}))
    try {
      const r = await apiClient.reason(reasonTest.task, reasonTest.strategy)
      setReasonTest(s => ({...s, running:false, result:r}))
    } catch(e) { setReasonTest(s => ({...s, running:false, result:{error:e.message}})) }
  }

  const statusColor = {
    healthy: "#10b981", degraded: "#f59e0b", failed: "#ef4444", unknown: "#888", recovering: "#6366f1"
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>⬟ System Dashboard</h2>
        <p className="panel-sub">Health monitoring, self-healing, and reasoning engine tester</p>
      </div>

      <div className="panel-body">
        {/* Overall health */}
        <div className="sys-section">
          <div className="section-title">System Health</div>
          <div className="health-grid">
            {healStatus?.components && Object.entries(healStatus.components).map(([name, info]) => (
              <div key={name} className="health-comp">
                <div className="comp-name">
                  <span className="comp-dot" style={{background: statusColor[info.status]||"#888"}} />
                  {name}
                </div>
                <div className="comp-status">{info.status}</div>
                <div className="comp-latency">{info.latency_ms?.toFixed(0)}ms</div>
                {info.error && <div className="comp-error">{info.error.slice(0,60)}</div>}
                <button className="btn-repair" onClick={()=>forceRepair(name)} disabled={loading}>
                  ↺ Repair
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Models */}
        {health?.models?.length > 0 && (
          <div className="sys-section">
            <div className="section-title">Ollama Models</div>
            <div className="model-list">
              {health.models.map(m => (
                <div key={m} className="model-item">
                  <span className="model-dot" />
                  <span>{m}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Repair Log */}
        {repairLog.length > 0 && (
          <div className="sys-section">
            <div className="section-title">Self-Healing Log</div>
            <div className="repair-log">
              {repairLog.slice().reverse().map((r, i) => (
                <div key={i} className={`repair-item ${r.success?"rep-ok":"rep-fail"}`}>
                  <span className="rep-icon">{r.success?"✅":"⚠️"}</span>
                  <span className="rep-comp">{r.component}</span>
                  <span className="rep-action">{r.action}</span>
                  <span className="rep-msg">{r.message?.slice(0,80)}</span>
                  <span className="rep-time">{new Date(r.timestamp*1000).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reasoning Tester */}
        <div className="sys-section">
          <div className="section-title">Reasoning Engine Tester</div>
          <div className="input-row">
            <input className="panel-input" placeholder="Enter a task to reason about…"
              value={reasonTest.task}
              onChange={e=>setReasonTest(s=>({...s,task:e.target.value}))}
              onKeyDown={e=>e.key==="Enter"&&runReason()} />
            <select className="panel-select"
              value={reasonTest.strategy}
              onChange={e=>setReasonTest(s=>({...s,strategy:e.target.value}))}>
              <option value="auto">Auto</option>
              <option value="cot">Chain of Thought</option>
              <option value="tot">Tree of Thought</option>
              <option value="reflect">Reflect</option>
            </select>
            <button className="btn-sm" onClick={runReason} disabled={reasonTest.running}>
              {reasonTest.running ? <span className="spinner-sm"/> : "Think"}
            </button>
          </div>
          {reasonTest.result && (
            <div className="result-card">
              <div className="result-header">
                Strategy: <b>{reasonTest.result.strategy}</b>
                {reasonTest.result.score > 0 && <span className="result-score">{reasonTest.result.score}/10</span>}
              </div>
              {reasonTest.result.thinking && (
                <details className="think-details">
                  <summary>Thinking process</summary>
                  <pre>{reasonTest.result.thinking}</pre>
                </details>
              )}
              <div className="answer-block">{reasonTest.result.answer || reasonTest.result.error}</div>
            </div>
          )}
        </div>

        {/* Version info */}
        <div className="sys-section">
          <div className="section-title">Version Info</div>
          <div className="version-grid">
            {[["API Version","3.0.0"],["Reasoning","Chain/Tree of Thought + Reflection"],
              ["Memory","ChromaDB Vector DB"],["Agents","Architect, Coder, Analyzer, Researcher"],
              ["Self-Healing","Background monitor (60s interval)"],
              ["Skill Learning","Auto-extract from interactions (score≥6)"]].map(([k,v])=>(
              <div key={k} className="ver-row"><span className="ver-key">{k}</span><span className="ver-val">{v}</span></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
