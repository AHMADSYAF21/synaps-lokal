import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function BenchmarkPanel() {
  const [suites, setSuites]   = useState({})
  const [runs, setRuns]       = useState([])
  const [selectedSuite, setSelectedSuite] = useState('coding')
  const [model, setModel]     = useState('')
  const [output, setOutput]   = useState('')
  const [running, setRunning] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const [models, setModels]   = useState([])

  useEffect(() => {
    apiClient.benchmarkSuites().then(r => setSuites(r.suites || {})).catch(()=>{})
    apiClient.benchmarkRuns().then(r => setRuns(r.runs || [])).catch(()=>{})
    apiClient.routerModels().then(r => setModels((r.models||[]).map(m=>m.name))).catch(()=>{})
  }, [])

  async function handleRun() {
    if (running) return
    setRunning(true); setOutput(''); setLastResult(null)

    const cancel = apiClient.benchmarkRun(
      selectedSuite, model,
      chunk => {
        if (chunk.startsWith('[BENCH_START]')) return
        setOutput(p => p + chunk)
      },
      data => {
        if (data.type === 'bench_done') {
          setLastResult(data)
          apiClient.benchmarkRuns().then(r => setRuns(r.runs || []))
        }
        setRunning(false)
      },
      e => { setOutput(p => p + `\nError: ${e.message}`); setRunning(false) }
    )
  }

  const gradeColor = score =>
    score >= 8 ? '#10b981' : score >= 6 ? '#f59e0b' : '#ef4444'

  const grade = score =>
    score >= 9 ? 'A+' : score >= 8 ? 'A' : score >= 7 ? 'B' :
    score >= 6 ? 'C' : score >= 5 ? 'D' : 'F'

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>📊 Benchmark Engine</h2>
        <p className="panel-sub">Test AI quality across coding, reasoning, and language tasks</p>
      </div>

      <div className="panel-body">
        <div className="control-row">
          <select className="panel-select" value={selectedSuite}
            onChange={e => setSelectedSuite(e.target.value)}>
            {Object.entries(suites).map(([name, count]) => (
              <option key={name} value={name}>{name} ({count} tests)</option>
            ))}
          </select>
          <select className="panel-select" value={model}
            onChange={e => setModel(e.target.value)}>
            <option value="">Default model</option>
            {models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <button className="btn-run" onClick={handleRun} disabled={running}>
            {running ? <><span className="spinner-sm"/> Running…</> : '▶ Run Benchmark'}
          </button>
        </div>

        {lastResult && (
          <div className="bench-result">
            <div className="bench-grade"
              style={{color: gradeColor(lastResult.avg)}}>
              {grade(lastResult.avg)}
            </div>
            <div className="bench-stats">
              <span>Score: <b>{lastResult.avg}/10</b></span>
              <span>Passed: <b>{lastResult.passed}/{lastResult.total}</b></span>
            </div>
          </div>
        )}

        {output && (
          <div className="output-block">
            <pre style={{whiteSpace:'pre-wrap',fontFamily:'var(--font-mono)',fontSize:12,lineHeight:1.6}}>
              {output}
            </pre>
          </div>
        )}

        {runs.length > 0 && (
          <div>
            <div className="section-title">Past Runs</div>
            <div className="bench-runs">
              {runs.map((r, i) => (
                <div key={i} className="bench-run-item">
                  <span className="bench-run-suite">{r.suite}</span>
                  <span className="bench-run-model">{r.model}</span>
                  <span className="bench-run-score"
                    style={{color: gradeColor(r.avg_score)}}>
                    {grade(r.avg_score)} {r.avg_score}/10
                  </span>
                  <span className="bench-run-pass">{r.passed}/{r.total}</span>
                  <span className="bench-run-date">
                    {new Date(r.finished_at*1000).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
