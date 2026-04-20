import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

const MODE_ICONS = { debate:'⚔️', council:'🏛️', pipeline:'🔗', peer_review:'📝', brainstorm:'💡' }

export default function CollabPanel() {
  const [modes, setModes]   = useState({})
  const [roles, setRoles]   = useState({})
  const [mode, setMode]     = useState('council')
  const [topic, setTopic]   = useState('')
  const [selRoles, setSelRoles] = useState([])
  const [rounds, setRounds] = useState(2)
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    apiClient.collabModes().then(r => setModes(r.modes||{})).catch(()=>{})
    apiClient.collabRoles().then(r => setRoles(r.roles||{})).catch(()=>{})
  }, [])

  // Auto-select default agents for mode
  const defaultAgents = {
    debate:      ['optimist','critic'],
    council:     ['optimist','critic','pragmatist'],
    pipeline:    ['researcher','architect','pragmatist','critic'],
    peer_review: ['architect','critic','pragmatist'],
    brainstorm:  ['optimist','researcher','pragmatist'],
  }

  function toggleRole(roleId) {
    setSelRoles(prev =>
      prev.includes(roleId) ? prev.filter(r=>r!==roleId) : [...prev, roleId]
    )
  }

  async function handleRun() {
    if (!topic.trim() || running) return
    setRunning(true); setOutput('')
    const agents = selRoles.length > 0 ? selRoles : null

    const cancel = apiClient.collabRun(
      topic, mode, agents, rounds,
      chunk => {
        if (chunk.startsWith('[COLLAB_START]')) return
        setOutput(p => p + chunk)
      },
      () => setRunning(false),
      e => { setOutput(p => p + `\n[ERROR] ${e.message}`); setRunning(false) }
    )
  }

  const roleColors = {
    optimist:'#10b981', critic:'#ef4444', pragmatist:'#f59e0b',
    architect:'#6366f1', ethicist:'#8b5cf6', researcher:'#06b6d4',
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🤝 Multi-Agent Collaboration</h2>
        <p className="panel-sub">Multiple AI agents debate, build, and peer-review together</p>
      </div>

      <div className="panel-body">
        {/* Mode select */}
        <div className="collab-modes">
          {Object.entries(modes).map(([id, desc]) => (
            <button key={id}
              className={`collab-mode-btn ${mode===id?'active':''}`}
              onClick={() => setMode(id)}>
              <span>{MODE_ICONS[id]||'◈'} {id.replace('_',' ')}</span>
              <span className="mode-desc">{desc}</span>
            </button>
          ))}
        </div>

        {/* Agent select */}
        <div className="form-field">
          <label className="form-label">
            Agents (leave empty for defaults: {defaultAgents[mode]?.join(', ')})
          </label>
          <div className="agent-pills">
            {Object.entries(roles).map(([id, info]) => (
              <button key={id}
                className={`agent-pill ${selRoles.includes(id)?'selected':''}`}
                style={selRoles.includes(id)?{borderColor:roleColors[id],color:roleColors[id]}:{}}
                onClick={() => toggleRole(id)}>
                {info.icon} {id}
              </button>
            ))}
          </div>
        </div>

        {/* Rounds (for debate) */}
        {mode === 'debate' && (
          <div className="control-row">
            <label className="form-label">Rounds:</label>
            {[1,2,3].map(n => (
              <button key={n} className={`task-btn ${rounds===n?'active':''}`}
                style={{minWidth:40}} onClick={()=>setRounds(n)}>{n}</button>
            ))}
          </div>
        )}

        {/* Topic input */}
        <div className="input-row">
          <textarea className="panel-textarea" rows={3}
            placeholder={`Enter topic for ${mode}…`}
            value={topic} onChange={e=>setTopic(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&e.ctrlKey)handleRun()}}/>
          <button className="btn-run" onClick={handleRun}
            disabled={running||!topic.trim()}>
            {running?<span className="spinner-sm"/>:`${MODE_ICONS[mode]||'▶'} Start`}
          </button>
        </div>

        {output && (
          <div className="output-block collab-output">
            <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.8}}>
              {output}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
