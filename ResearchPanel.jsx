import { useState } from 'react'
import { apiClient } from '../api/client'

const DEPTHS = [
  { id:'quick',    label:'⚡ Quick',    desc:'2 queries, fast' },
  { id:'standard', label:'📊 Standard', desc:'4 queries, balanced' },
  { id:'deep',     label:'🔬 Deep',     desc:'6 queries, thorough' },
]

export default function ResearchPanel() {
  const [topic, setTopic]   = useState('')
  const [depth, setDepth]   = useState('standard')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [citations, setCitations] = useState([])

  async function handleResearch() {
    if (!topic.trim() || running) return
    setRunning(true); setOutput(''); setCitations([])

    apiClient.researchStream(
      topic, depth,
      chunk => {
        setOutput(p => p + chunk)
      },
      () => setRunning(false),
      e => { setOutput(p => p + `\n[ERROR] ${e.message}`); setRunning(false) }
    )
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🔬 Deep Researcher</h2>
        <p className="panel-sub">
          Plans queries → searches in parallel → extracts → cross-references → synthesises
        </p>
      </div>

      <div className="panel-body">
        {/* Depth selector */}
        <div className="collab-modes">
          {DEPTHS.map(d => (
            <button key={d.id}
              className={`collab-mode-btn ${depth===d.id?'active':''}`}
              onClick={() => setDepth(d.id)}>
              <span>{d.label}</span>
              <span className="mode-desc">{d.desc}</span>
            </button>
          ))}
        </div>

        {/* Topic input */}
        <div className="input-row">
          <input className="panel-input"
            placeholder="Research topic… e.g. 'latest advances in quantum computing'"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleResearch()}
          />
          <button className="btn-run" onClick={handleResearch}
            disabled={running || !topic.trim()}>
            {running ? <span className="spinner-sm"/> : '🔬 Research'}
          </button>
        </div>

        {running && (
          <div className="research-progress">
            <span className="record-pulse">🔍 Researching… (this takes 30-60s)</span>
          </div>
        )}

        {output && (
          <div className="output-block research-output">
            <pre style={{
              whiteSpace: 'pre-wrap',
              fontFamily: 'inherit',
              fontSize: 13,
              lineHeight: 1.8,
            }}>
              {output}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
