import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function PromptsPanel() {
  const [templates, setTemplates] = useState([])
  const [stats, setStats]         = useState(null)
  const [categories, setCategories] = useState([])
  const [search, setSearch]       = useState('')
  const [selCat, setSelCat]       = useState('')
  const [selected, setSelected]   = useState(null)
  const [variables, setVariables] = useState({})
  const [result, setResult]       = useState('')
  const [tab, setTab]             = useState('browse')
  const [loading, setLoading]     = useState(false)
  const [generating, setGenerating] = useState(false)
  const [genReq, setGenReq]       = useState({ use_case:'', category:'general', example:'' })
  const [newTpl, setNewTpl]       = useState({ name:'', template:'', category:'general', description:'' })

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [t, c] = await Promise.all([
        apiClient.listPrompts('', '', 100),
        apiClient.promptCategories(),
      ])
      setTemplates(t.templates || [])
      setStats(t.stats)
      setCategories(c.categories || [])
    } catch(e) { console.error(e) }
  }

  async function handleSearch() {
    const r = await apiClient.listPrompts(selCat, search, 100)
    setTemplates(r.templates || [])
  }

  function selectTemplate(t) {
    setSelected(t)
    setResult('')
    // Init variable fields
    const vars = {}
    ;(t.variables || []).forEach(v => vars[v] = '')
    setVariables(vars)
  }

  async function handleApply() {
    if (!selected) return
    const r = await apiClient.applyPrompt(selected.template_id, variables)
    setResult(r.prompt || '')
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(result || selected?.template || '')
    alert('Copied to clipboard!')
  }

  async function handleImprove() {
    if (!selected) return
    setLoading(true)
    const r = await apiClient.improvePrompt(selected.template_id)
    setSelected(s => ({...s, template: r.template}))
    setLoading(false)
  }

  async function handleGenerate() {
    if (!genReq.use_case.trim()) return
    setGenerating(true)
    try {
      const r = await apiClient.generatePrompt(genReq)
      setTemplates(p => [r, ...p])
      selectTemplate(r)
      setTab('browse')
    } catch(e) { alert(e.message) }
    finally { setGenerating(false) }
  }

  async function handleCreate() {
    if (!newTpl.name.trim() || !newTpl.template.trim()) return
    setLoading(true)
    const r = await apiClient.createPrompt(newTpl)
    setTemplates(p => [r, ...p])
    setNewTpl({ name:'', template:'', category:'general', description:'' })
    setLoading(false)
  }

  async function handleDelete(id) {
    if (!confirm('Delete this template?')) return
    await apiClient.deletePrompt(id)
    setTemplates(p => p.filter(t => t.template_id !== id))
    if (selected?.template_id === id) setSelected(null)
  }

  const catColors = {
    coding:'#10b981', writing:'#06b6d4', education:'#f59e0b',
    data:'#6366f1', architecture:'#8b5cf6', testing:'#ef4444',
    productivity:'#10b981', general:'#888',
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>📜 Prompt Library</h2>
        <p className="panel-sub">{stats?.total||0} templates · {stats?.categories||0} categories · AI-powered generation</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total}</span><span>Templates</span></div>
          <div className="stat-box"><span className="stat-n">{stats.categories}</span><span>Categories</span></div>
          {stats.top_used?.slice(0,1).map(t=>(
            <div key={t.name} className="stat-box">
              <span className="stat-n meta-accent">{t.uses}×</span>
              <span>{t.name?.slice(0,12)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="memory-tabs">
        {['browse','apply','create','generate'].map(t=>(
          <button key={t} className={`mem-tab ${tab===t?'active':''}`} onClick={()=>setTab(t)}>
            {t==='browse'?'Browse':t==='apply'?'Apply':t==='create'?'Create':'✨ AI Generate'}
          </button>
        ))}
      </div>

      <div className="panel-body">
        {/* BROWSE */}
        {tab === 'browse' && (
          <div>
            <div className="control-row">
              <input className="panel-input" placeholder="Search templates…"
                value={search} onChange={e=>setSearch(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&handleSearch()}/>
              <select className="panel-select" value={selCat} onChange={e=>{setSelCat(e.target.value);handleSearch()}}>
                <option value="">All categories</option>
                {categories.map(c=><option key={c} value={c}>{c}</option>)}
              </select>
              <button className="btn-sm" onClick={handleSearch}>Filter</button>
            </div>

            <div className="skill-list">
              {templates.map(t=>(
                <div key={t.template_id}
                  className={`skill-card ${selected?.template_id===t.template_id?'selected-card':''}`}
                  style={{cursor:'pointer',borderColor:selected?.template_id===t.template_id?'var(--accent)':'var(--border)'}}
                  onClick={()=>selectTemplate(t)}>
                  <div className="skill-header">
                    <span className="skill-type-dot" style={{background:catColors[t.category]||'#888'}}/>
                    <span className="skill-name">{t.name}</span>
                    {t.is_builtin && <span className="mem-tag">builtin</span>}
                    <span className="mem-tag" style={{color:catColors[t.category]||'#888'}}>{t.category}</span>
                    <span className="skill-uses">{t.use_count}×</span>
                    {!t.is_builtin && <button className="del-btn" onClick={e=>{e.stopPropagation();handleDelete(t.template_id)}}>✕</button>}
                  </div>
                  <p className="skill-desc">{t.description}</p>
                  {t.variables?.length > 0 && (
                    <div className="skill-tags">
                      {t.variables.map(v=><span key={v} className="mem-tag">&#123;&#123;{v}&#125;&#125;</span>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* APPLY */}
        {tab === 'apply' && (
          <div>
            {!selected ? (
              <div className="memory-empty">Select a template from Browse to apply it</div>
            ) : (
              <div>
                <div className="distill-card" style={{marginBottom:12}}>
                  <div className="distill-title">{selected.name}</div>
                  <pre style={{fontFamily:'var(--font-mono)',fontSize:11,whiteSpace:'pre-wrap',color:'var(--text-dim)'}}>
                    {selected.template}
                  </pre>
                </div>

                {Object.keys(variables).length > 0 && (
                  <div>
                    <div className="section-title">Fill in variables:</div>
                    {Object.keys(variables).map(v=>(
                      <div key={v} className="form-field">
                        <label className="form-label">&#123;&#123;{v}&#125;&#125;</label>
                        <textarea className="panel-textarea" rows={2}
                          value={variables[v]} onChange={e=>setVariables(prev=>({...prev,[v]:e.target.value}))}/>
                      </div>
                    ))}
                  </div>
                )}

                <div className="btn-row">
                  <button className="btn-run" onClick={handleApply}>Apply Template</button>
                  <button className="btn-sm" onClick={handleImprove} disabled={loading}>
                    {loading?<span className="spinner-sm"/>:'✨ AI Improve'}
                  </button>
                </div>

                {result && (
                  <div>
                    <div className="section-title" style={{marginBottom:6}}>Generated Prompt:</div>
                    <div className="output-block">
                      <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13}}>{result}</pre>
                    </div>
                    <button className="btn-sm" onClick={handleCopy} style={{marginTop:8}}>📋 Copy</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* CREATE */}
        {tab === 'create' && (
          <div>
            {[['name','Name *','Template name'],['description','Description','Brief description']].map(([k,l,p])=>(
              <div key={k} className="form-field">
                <label className="form-label">{l}</label>
                <input className="panel-input" placeholder={p}
                  value={newTpl[k]} onChange={e=>setNewTpl(t=>({...t,[k]:e.target.value}))}/>
              </div>
            ))}
            <div className="form-field">
              <label className="form-label">Category</label>
              <select className="panel-select full-width" value={newTpl.category}
                onChange={e=>setNewTpl(t=>({...t,category:e.target.value}))}>
                {['general','coding','writing','education','data','architecture','testing','productivity'].map(c=>(
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">Template (use &#123;&#123;variable_name&#125;&#125; for dynamic parts)</label>
              <textarea className="panel-textarea code-ta" rows={8}
                placeholder="Write your prompt template here…&#10;Use {{variable}} for dynamic parts."
                value={newTpl.template} onChange={e=>setNewTpl(t=>({...t,template:e.target.value}))}/>
            </div>
            <button className="btn-run" onClick={handleCreate} disabled={loading||!newTpl.name.trim()||!newTpl.template.trim()}>
              {loading?<span className="spinner-sm"/>:'Save Template'}
            </button>
          </div>
        )}

        {/* AI GENERATE */}
        {tab === 'generate' && (
          <div>
            <p className="panel-hint">Describe your use case — AI writes an optimised prompt template</p>
            <div className="form-field">
              <label className="form-label">Use case *</label>
              <input className="panel-input" placeholder="e.g. 'Summarise legal documents into plain language'"
                value={genReq.use_case} onChange={e=>setGenReq(r=>({...r,use_case:e.target.value}))}/>
            </div>
            <div className="form-field">
              <label className="form-label">Category</label>
              <select className="panel-select full-width" value={genReq.category}
                onChange={e=>setGenReq(r=>({...r,category:e.target.value}))}>
                {['general','coding','writing','education','data','architecture','testing','productivity'].map(c=>(
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">Example input (optional)</label>
              <textarea className="panel-textarea" rows={2}
                placeholder="What kind of input will this prompt receive?"
                value={genReq.example} onChange={e=>setGenReq(r=>({...r,example:e.target.value}))}/>
            </div>
            <button className="btn-run" onClick={handleGenerate}
              disabled={generating||!genReq.use_case.trim()}>
              {generating?<><span className="spinner-sm"/> Generating…</>:'✨ Generate Template'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
