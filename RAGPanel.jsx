import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

export default function RAGPanel() {
  const [docs, setDocs]         = useState([])
  const [stats, setStats]       = useState(null)
  const [question, setQuestion] = useState('')
  const [docId, setDocId]       = useState('')
  const [answer, setAnswer]     = useState('')
  const [sources, setSources]   = useState([])
  const [uploading, setUploading] = useState(false)
  const [querying, setQuerying]   = useState(false)
  const [tab, setTab]           = useState('query')
  const [summary, setSummary]   = useState('')
  const fileRef = useRef(null)

  useEffect(() => { loadDocs() }, [])

  async function loadDocs() {
    try {
      const r = await apiClient.listRAGDocs()
      setDocs(r.documents || [])
      setStats(r.stats)
    } catch(e) { console.error(e) }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const r = await apiClient.uploadRAGDoc(file)
      if (r.success) { await loadDocs(); alert(`✅ Indexed: ${r.filename} (${r.chunks} chunks)`) }
      else alert(`❌ ${r.error}`)
    } catch(err) { alert(`Error: ${err.message}`) }
    finally { setUploading(false); e.target.value = '' }
  }

  async function handleQuery() {
    if (!question.trim() || querying) return
    setQuerying(true); setAnswer(''); setSources([])
    try {
      const cancel = apiClient.ragQueryStream(
        question, docId || null, 6,
        chunk => {
          if (chunk.startsWith('[SOURCES:')) {
            const m = chunk.match(/\[SOURCES: (.+?)\]/)
            if (m) setSources(m[1].split(',').map(s => s.trim()))
          } else {
            setAnswer(p => p + chunk)
          }
        },
        () => setQuerying(false),
        e => { setAnswer(`Error: ${e.message}`); setQuerying(false) }
      )
    } catch(e) { setAnswer(`Error: ${e.message}`); setQuerying(false) }
  }

  async function handleSummarise(id) {
    setSummary('Summarising…')
    const r = await apiClient.ragSummarise(id)
    setSummary(r.summary || r.error || 'Failed')
  }

  async function handleDelete(id) {
    if (!confirm('Delete this document?')) return
    await apiClient.deleteRAGDoc(id)
    await loadDocs()
    if (docId === id) setDocId('')
  }

  const typeIcon = { pdf:'📄', txt:'📝', md:'📋', docx:'📃', csv:'📊', json:'🔧' }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>📄 Document Q&A (RAG)</h2>
        <p className="panel-sub">Upload documents → ask questions → AI answers from your files</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total_documents}</span><span>Docs</span></div>
          <div className="stat-box"><span className="stat-n">{stats.total_chunks}</span><span>Chunks</span></div>
          <div className="stat-box"><span className="stat-n">{stats.total_size_kb}KB</span><span>Indexed</span></div>
        </div>
      )}

      <div className="memory-tabs">
        {['query','documents'].map(t => (
          <button key={t} className={`mem-tab ${tab===t?'active':''}`} onClick={()=>setTab(t)}>
            {t === 'query' ? '🔍 Ask' : '📁 Documents'}
          </button>
        ))}
      </div>

      <div className="panel-body">
        {tab === 'query' && (
          <div>
            <div className="form-field">
              <label className="form-label">Filter by document (optional)</label>
              <select className="panel-select full-width" value={docId} onChange={e=>setDocId(e.target.value)}>
                <option value="">All documents</option>
                {docs.map(d => <option key={d.doc_id} value={d.doc_id}>{d.name}</option>)}
              </select>
            </div>

            <div className="input-row">
              <textarea className="panel-textarea" rows={3}
                placeholder="Ask anything about your documents…"
                value={question} onChange={e=>setQuestion(e.target.value)}
                onKeyDown={e => { if(e.key==='Enter'&&e.ctrlKey) handleQuery() }}/>
              <button className="btn-run" onClick={handleQuery} disabled={querying||!question.trim()}>
                {querying ? <span className="spinner-sm"/> : '🔍 Ask'}
              </button>
            </div>

            {sources.length > 0 && (
              <div className="rag-sources">
                {sources.map((s,i) => <span key={i} className="source-tag">📄 {s}</span>)}
              </div>
            )}

            {answer && (
              <div className="output-block">
                <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13}}>{answer}</pre>
              </div>
            )}

            {docs.length === 0 && (
              <div className="memory-empty">
                No documents indexed yet — upload files in the Documents tab
              </div>
            )}
          </div>
        )}

        {tab === 'documents' && (
          <div>
            <div className="upload-area" onClick={()=>fileRef.current?.click()}>
              <input ref={fileRef} type="file" hidden
                accept=".pdf,.txt,.md,.docx,.csv,.json"
                onChange={handleUpload}/>
              <div className="upload-icon">{uploading ? '⏳' : '⬆'}</div>
              <div className="upload-text">
                {uploading ? 'Indexing…' : 'Click to upload or drag & drop'}
              </div>
              <div className="upload-hint">PDF · TXT · MD · DOCX · CSV · JSON · max 50MB</div>
            </div>

            {summary && (
              <div className="output-block" style={{marginTop:8}}>
                <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:12}}>{summary}</pre>
              </div>
            )}

            {docs.length === 0 ? (
              <div className="memory-empty">No documents indexed yet</div>
            ) : (
              <div className="skill-list">
                {docs.map(d => (
                  <div key={d.doc_id} className="skill-card">
                    <div className="skill-header">
                      <span style={{fontSize:18}}>{typeIcon[d.file_type]||'📄'}</span>
                      <span className="skill-name">{d.name}</span>
                      <span className="skill-score">{d.chunks} chunks</span>
                      <span className="skill-uses">{d.size_kb}KB</span>
                      <button className="btn-sm" style={{fontSize:10,padding:'3px 8px'}}
                        onClick={()=>handleSummarise(d.doc_id)}>Summarise</button>
                      <button className="del-btn" onClick={()=>handleDelete(d.doc_id)}>✕</button>
                    </div>
                    <div className="skill-desc">
                      Indexed {new Date(d.created_at*1000).toLocaleDateString()}
                    </div>
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
