import { useState, useEffect } from "react"
import { apiClient } from "../api/client"

export default function CapabilityPanel() {
  const [caps, setCaps] = useState([])
  const [allTools, setAllTools] = useState([])
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState("list")
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ tool_name:"", tool_description:"", tool_purpose:"", example_params:"{}" })
  const [createResult, setCreateResult] = useState(null)
  const [detectInput, setDetectInput] = useState("")
  const [detectResult, setDetectResult] = useState(null)
  const [expandResult, setExpandResult] = useState(null)
  const [testTool, setTestTool] = useState("")
  const [testParams, setTestParams] = useState("{}")
  const [testResult, setTestResult] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const r = await apiClient.listCapabilities()
      setCaps(r.created_tools || [])
      setAllTools(r.all_tools || [])
      setStats(r.stats)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  async function handleCreate() {
    setLoading(true); setCreateResult(null)
    try {
      let params = {}
      try { params = JSON.parse(form.example_params||"{}") } catch {}
      const r = await apiClient.createTool({ ...form, example_params: params, test_after_create: true })
      setCreateResult(r)
      if (r.success) await load()
    } catch(e) { setCreateResult({ success:false, error:e.message }) }
    finally { setLoading(false) }
  }

  async function handleDetect() {
    if (!detectInput.trim()) return
    setLoading(true)
    const r = await apiClient.detectGap(detectInput, "")
    setDetectResult(r)
    setLoading(false)
  }

  async function handleAutoExpand() {
    if (!detectInput.trim()) return
    setLoading(true); setExpandResult(null)
    const r = await apiClient.autoExpand(detectInput, "")
    setExpandResult(r)
    if (r.success) await load()
    setLoading(false)
  }

  async function handleTest() {
    if (!testTool) return
    setLoading(true); setTestResult(null)
    try {
      let params = {}
      try { params = JSON.parse(testParams||"{}") } catch {}
      const r = await apiClient.runTool(testTool, params)
      setTestResult(r)
    } catch(e) { setTestResult({ error: e.message }) }
    finally { setLoading(false) }
  }

  async function handleDelete(name) {
    await apiClient.deleteCapability(name)
    await load()
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>⊕ Capability Engine</h2>
        <p className="panel-sub">AI writes, tests, and registers new tools autonomously</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total_created}</span><span>Created</span></div>
          <div className="stat-box"><span className="stat-n">{stats.currently_registered}</span><span>Active</span></div>
        </div>
      )}

      <div className="memory-tabs">
        {[["list","All Tools"],["detect","Auto-Detect"],["create","Create Tool"],["test","Test Tool"]].map(([id,label])=>(
          <button key={id} className={`mem-tab ${tab===id?"active":""}`} onClick={()=>setTab(id)}>{label}</button>
        ))}
      </div>

      <div className="panel-body">
        {/* LIST */}
        {tab==="list" && (
          <>
            <div className="tools-section">
              <div className="section-title">Built-in Tools ({allTools.length - caps.length})</div>
              <div className="tool-grid">
                {allTools.filter(t=>!caps.find(c=>c.name===t.name)).map(t=>(
                  <div key={t.name} className="tool-card builtin">
                    <div className="tool-name">⚙ {t.name}</div>
                    <div className="tool-desc">{t.description}</div>
                  </div>
                ))}
              </div>
            </div>
            {caps.length > 0 && (
              <div className="tools-section">
                <div className="section-title">AI-Created Tools ({caps.length})</div>
                <div className="tool-grid">
                  {caps.map(c=>(
                    <div key={c.name} className="tool-card created">
                      <div className="tool-name">
                        <span className="created-dot">⊕</span> {c.name}
                        <button className="del-btn" onClick={()=>handleDelete(c.name)}>✕</button>
                      </div>
                      <div className="tool-desc">{c.description}</div>
                      <div className="tool-meta">{c.file} · {c.size}B</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* DETECT */}
        {tab==="detect" && (
          <div>
            <p className="panel-hint">Describe a task. AI checks if existing tools can handle it or if a new tool is needed.</p>
            <div className="input-row">
              <textarea className="panel-textarea" rows={2}
                placeholder="e.g. 'I need to compress images' or 'Parse PDF files'"
                value={detectInput} onChange={e=>setDetectInput(e.target.value)} />
            </div>
            <div className="btn-row">
              <button className="btn-run" onClick={handleDetect} disabled={loading}>🔍 Detect Gap</button>
              <button className="btn-run btn-amber" onClick={handleAutoExpand} disabled={loading}>⊕ Auto-Create</button>
            </div>

            {detectResult && (
              <div className={`result-card ${detectResult.gap_detected?"warn":"success"}`}>
                <div className="result-header">
                  {detectResult.gap_detected
                    ? `⚠️ Gap detected: ${detectResult.analysis?.tool_name}`
                    : "✅ No gap — existing tools sufficient"}
                </div>
                {detectResult.analysis && (
                  <div className="analysis-block">
                    <div><b>Tool:</b> {detectResult.analysis.tool_name}</div>
                    <div><b>Description:</b> {detectResult.analysis.tool_description}</div>
                    <div><b>Confidence:</b> {(detectResult.analysis.confidence*100).toFixed(0)}%</div>
                  </div>
                )}
              </div>
            )}

            {expandResult && (
              <div className={`result-card ${expandResult.success?"success":"warn"}`}>
                <div className="result-header">
                  {expandResult.success ? `✅ Created: ${expandResult.tool_name}` : `✗ ${expandResult.message||expandResult.error}`}
                </div>
                {expandResult.success && expandResult.code && (
                  <pre className="final-code">{expandResult.code.slice(0,800)}</pre>
                )}
                {expandResult.test && (
                  <div className="test-result">
                    Test: {expandResult.test.passed ? "✅ passed" : "⚠️ failed"}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* CREATE */}
        {tab==="create" && (
          <div>
            <p className="panel-hint">Manually specify a tool. AI writes the Python class, tests it, and registers it.</p>
            {[["tool_name","Tool name (snake_case)","e.g. image_resizer"],
              ["tool_description","Description","What this tool does"],
              ["tool_purpose","Purpose","Why it's needed"],
              ["example_params","Example params (JSON)","{ \"input\": \"value\" }"]].map(([k,label,ph])=>(
              <div key={k} className="form-field">
                <label className="form-label">{label}</label>
                {k==="example_params"
                  ? <textarea className="panel-textarea code-ta" rows={3} placeholder={ph}
                      value={form[k]} onChange={e=>setForm(f=>({...f,[k]:e.target.value}))} />
                  : <input className="panel-input" placeholder={ph}
                      value={form[k]} onChange={e=>setForm(f=>({...f,[k]:e.target.value}))} />
                }
              </div>
            ))}
            <button className="btn-run" onClick={handleCreate} disabled={loading||!form.tool_name}>
              {loading ? <><span className="spinner-sm"/> Writing tool…</> : "⊕ Create Tool"}
            </button>

            {createResult && (
              <div className={`result-card ${createResult.success?"success":"warn"}`}>
                <div className="result-header">
                  {createResult.success ? `✅ ${createResult.message}` : `✗ ${createResult.error}`}
                </div>
                {createResult.test && (
                  <div className="test-result">Test run: {createResult.test.passed?"✅ passed":"⚠️ failed"}</div>
                )}
                {createResult.code && <pre className="final-code">{createResult.code.slice(0,600)}</pre>}
              </div>
            )}
          </div>
        )}

        {/* TEST */}
        {tab==="test" && (
          <div>
            <p className="panel-hint">Run any registered tool with custom params.</p>
            <div className="form-field">
              <label className="form-label">Select Tool</label>
              <select className="panel-select full-width" value={testTool} onChange={e=>setTestTool(e.target.value)}>
                <option value="">— choose tool —</option>
                {allTools.map(t=><option key={t.name} value={t.name}>{t.name}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">Params (JSON)</label>
              <textarea className="panel-textarea code-ta" rows={4}
                value={testParams} onChange={e=>setTestParams(e.target.value)} />
            </div>
            <button className="btn-run" onClick={handleTest} disabled={loading||!testTool}>
              {loading ? <span className="spinner-sm"/> : "▶ Run Tool"}
            </button>
            {testResult && (
              <div className="result-card">
                <pre className="final-code">{JSON.stringify(testResult, null, 2).slice(0,1500)}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
