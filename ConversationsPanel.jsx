import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function ConversationsPanel() {
  const [sessions, setSessions] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [search, setSearch]     = useState('')
  const [selected, setSelected] = useState(null)
  const [messages, setMessages] = useState([])
  const [summary, setSummary]   = useState('')
  const [loading, setLoading]   = useState(false)
  const [tab, setTab]           = useState('list')

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [s, a] = await Promise.all([
        apiClient.listConversations(50, 0, ''),
        apiClient.convAnalytics(),
      ])
      setSessions(s.sessions || [])
      setAnalytics(a)
    } catch(e) { console.error(e) }
  }

  async function handleSearch() {
    if (!search.trim()) { await loadAll(); return }
    setLoading(true)
    try {
      const r = await apiClient.listConversations(50, 0, search)
      setSessions(r.sessions || [])
    } catch(e) {}
    finally { setLoading(false) }
  }

  async function openSession(sess) {
    setSelected(sess); setMessages([]); setSummary('')
    setLoading(true)
    try {
      const r = await apiClient.getConversationMessages(sess.session_id)
      setMessages(r.messages || [])
    } catch(e) {}
    finally { setLoading(false); setTab('messages') }
  }

  async function handleSummarise() {
    if (!selected) return
    setLoading(true)
    try {
      const r = await apiClient.summariseConversation(selected.session_id)
      setSummary(r.summary || '')
      // Refresh session list
      await loadAll()
    } catch(e) {}
    finally { setLoading(false) }
  }

  async function handleExport(fmt) {
    if (!selected) return
    try {
      const blob = await apiClient.exportConversation(selected.session_id, fmt)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = `session-${selected.session_id.slice(-8)}.${fmt}`
      a.click(); URL.revokeObjectURL(url)
    } catch(e) { alert(e.message) }
  }

  async function handleDelete(sessionId) {
    if (!confirm('Delete this conversation?')) return
    await apiClient.deleteConversation(sessionId)
    setSessions(s => s.filter(x => x.session_id !== sessionId))
    if (selected?.session_id === sessionId) {
      setSelected(null); setMessages([]); setTab('list')
    }
  }

  const fmtTime = ts => ts ? new Date(ts*1000).toLocaleString([], {
    month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'
  }) : ''

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>💬 Conversations</h2>
        <p className="panel-sub">Full history, search, export, and analytics</p>
      </div>

      {analytics && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{analytics.total_sessions}</span><span>Sessions</span></div>
          <div className="stat-box"><span className="stat-n">{analytics.total_messages}</span><span>Messages</span></div>
          <div className="stat-box"><span className="stat-n">{analytics.total_tokens_est}</span><span>Tokens est.</span></div>
          {analytics.agent_usage?.slice(0,1).map(a=>(
            <div key={a.agent} className="stat-box">
              <span className="stat-n meta-accent">{a.count}</span>
              <span>{a.agent}</span>
            </div>
          ))}
        </div>
      )}

      <div className="memory-tabs">
        <button className={`mem-tab ${tab==='list'?'active':''}`} onClick={()=>setTab('list')}>
          📋 Sessions ({sessions.length})
        </button>
        {selected && (
          <button className={`mem-tab ${tab==='messages'?'active':''}`} onClick={()=>setTab('messages')}>
            💬 {selected.title?.slice(0,20)}…
          </button>
        )}
        <button className={`mem-tab ${tab==='analytics'?'active':''}`} onClick={()=>setTab('analytics')}>
          📊 Analytics
        </button>
      </div>

      <div className="panel-body">
        {tab === 'list' && (
          <div>
            <div className="input-row">
              <input className="panel-input" placeholder="Search conversations…"
                value={search} onChange={e=>setSearch(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&handleSearch()}/>
              <button className="btn-sm" onClick={handleSearch} disabled={loading}>Search</button>
              {search && <button className="btn-sm-ghost" onClick={()=>{setSearch('');loadAll()}}>Clear</button>}
            </div>

            {sessions.length === 0 ? (
              <div className="memory-empty">No conversations yet — start chatting!</div>
            ) : (
              <div className="conv-list">
                {sessions.map(s => (
                  <div key={s.session_id} className="conv-item"
                    onClick={() => openSession(s)}>
                    <div className="conv-header">
                      <span className="conv-title">{s.title || 'Untitled'}</span>
                      <span className="conv-count">{s.message_count} msgs</span>
                      <button className="del-btn" onClick={e=>{e.stopPropagation();handleDelete(s.session_id)}}>✕</button>
                    </div>
                    <div className="conv-meta">
                      <span>{fmtTime(s.updated_at)}</span>
                      {s.topics?.slice(0,3).map(t=>(
                        <span key={t} className="mem-tag">{t}</span>
                      ))}
                    </div>
                    {s.summary && (
                      <p className="conv-summary">{s.summary.slice(0,100)}…</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'messages' && selected && (
          <div>
            <div className="conv-toolbar">
              <span className="conv-title">{selected.title}</span>
              <button className="btn-sm" onClick={handleSummarise} disabled={loading}>
                {loading?<span className="spinner-sm"/>:'📝 Summarise'}
              </button>
              {['markdown','json','text'].map(fmt=>(
                <button key={fmt} className="btn-sm-ghost"
                  onClick={()=>handleExport(fmt)}>
                  ↓ {fmt}
                </button>
              ))}
            </div>

            {summary && (
              <div className="distill-card" style={{marginBottom:10}}>
                <div className="distill-title">Summary</div>
                <p style={{fontSize:12,color:'var(--text-dim)'}}>{summary}</p>
              </div>
            )}

            <div className="msg-history">
              {messages.map(m => (
                <div key={m.msg_id} className={`history-msg ${m.role}`}>
                  <div className="history-meta">
                    <span className={m.role==='user'?'user-label':'ai-label'}>
                      {m.role==='user' ? 'YOU' : `◈ ${m.agent_role||'AI'}`}
                    </span>
                    <span className="msg-time">{fmtTime(m.timestamp)}</span>
                    {m.strategy && <span className="mem-tag">{m.strategy}</span>}
                  </div>
                  <p className="history-content">{m.content.slice(0,300)}
                    {m.content.length > 300 && '…'}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'analytics' && analytics && (
          <div>
            <div className="section-title">Top Sessions</div>
            {(analytics.most_active||[]).map(s=>(
              <div key={s.session_id} className="bench-run-item">
                <span className="bench-run-suite">{s.session_id.slice(-8)}</span>
                <span className="bench-run-model">{s.messages} messages</span>
              </div>
            ))}
            <div className="section-title" style={{marginTop:16}}>Agent Usage</div>
            {(analytics.agent_usage||[]).map(a=>(
              <div key={a.agent} className="bench-run-item">
                <span className="bench-run-suite">{a.agent}</span>
                <span className="bench-run-pass">{a.count} calls</span>
              </div>
            ))}
            <div className="section-title" style={{marginTop:16}}>Recent Topics</div>
            <div style={{display:'flex',flexWrap:'wrap',gap:6,marginTop:8}}>
              {(analytics.recent_topics||[]).map(t=>(
                <span key={t} className="mem-tag">{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
