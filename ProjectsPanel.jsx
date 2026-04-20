import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

const STATUS_COLORS = { active:'#10b981', paused:'#f59e0b', completed:'#6366f1', archived:'#888' }
const PRIORITY_LABELS = { 1:'🔵 Low', 2:'🟢 Normal', 3:'🟡 Medium', 4:'🟠 High', 5:'🔴 Critical' }

export default function ProjectsPanel() {
  const [projects, setProjects] = useState([])
  const [stats, setStats]       = useState(null)
  const [selected, setSelected] = useState(null)
  const [tasks, setTasks]       = useState([])
  const [notes, setNotes]       = useState([])
  const [files, setFiles]       = useState([])
  const [tab, setTab]           = useState('list')
  const [detailTab, setDetailTab] = useState('tasks')
  const [loading, setLoading]   = useState(false)
  const fileRef = useRef(null)

  // Create forms
  const [newProj, setNewProj]   = useState({ name:'', description:'', tech_stack:[], goals:[], ai_context:'' })
  const [newTask, setNewTask]   = useState({ title:'', description:'', priority:3 })
  const [newNote, setNewNote]   = useState({ title:'', content:'' })
  const [techInput, setTechInput] = useState('')
  const [goalInput, setGoalInput] = useState('')

  useEffect(() => { loadProjects() }, [])

  async function loadProjects() {
    setLoading(true)
    try {
      const r = await apiClient.listProjects()
      setProjects(r.projects || [])
      setStats(r.stats)
    } catch(e) {} finally { setLoading(false) }
  }

  async function openProject(p) {
    setSelected(p); setTab('detail'); setDetailTab('tasks')
    const [t, n, f] = await Promise.all([
      apiClient.listTasks(p.project_id),
      apiClient.listProjectNotes(p.project_id),
      apiClient.listProjectFiles(p.project_id),
    ])
    setTasks(t.tasks || [])
    setNotes(n.notes || [])
    setFiles(f.files || [])
  }

  async function handleCreateProject() {
    if (!newProj.name.trim()) return
    setLoading(true)
    const r = await apiClient.createProject(newProj)
    setProjects(p => [r, ...p])
    setNewProj({ name:'', description:'', tech_stack:[], goals:[], ai_context:'' })
    setTechInput(''); setGoalInput('')
    setLoading(false)
  }

  async function handleCreateTask() {
    if (!newTask.title.trim() || !selected) return
    const t = await apiClient.createTask(selected.project_id, newTask)
    setTasks(prev => [...prev, t])
    setNewTask({ title:'', description:'', priority:3 })
  }

  async function handleUpdateTaskStatus(taskId, status) {
    await apiClient.updateTask(selected.project_id, taskId, { status })
    setTasks(prev => prev.map(t => t.task_id===taskId ? {...t, status} : t))
  }

  async function handleDeleteTask(taskId) {
    await apiClient.deleteTask(selected.project_id, taskId)
    setTasks(prev => prev.filter(t => t.task_id !== taskId))
  }

  async function handleCreateNote() {
    if (!newNote.title.trim() || !selected) return
    const n = await apiClient.createProjectNote(selected.project_id, newNote)
    setNotes(prev => [n, ...prev])
    setNewNote({ title:'', content:'' })
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file || !selected) return
    const r = await apiClient.uploadProjectFile(selected.project_id, file)
    setFiles(prev => [...prev, r])
    e.target.value = ''
  }

  async function handleDeleteProject(id) {
    if (!confirm('Delete this project and all its data?')) return
    await apiClient.deleteProject(id)
    setProjects(p => p.filter(x => x.project_id !== id))
    if (selected?.project_id === id) { setSelected(null); setTab('list') }
  }

  const addTech  = () => { if(techInput.trim()){ setNewProj(p=>({...p,tech_stack:[...p.tech_stack,techInput.trim()]})); setTechInput('') }}
  const addGoal  = () => { if(goalInput.trim()){ setNewProj(p=>({...p,goals:[...p.goals,goalInput.trim()]})); setGoalInput('') }}

  const tasksByStatus = status => tasks.filter(t => t.status === status)

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>📁 Projects</h2>
        <p className="panel-sub">Organise work into projects with tasks, notes, files, and AI context</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total_projects}</span><span>Projects</span></div>
          <div className="stat-box"><span className="stat-n meta-accent">{stats.active}</span><span>Active</span></div>
          <div className="stat-box"><span className="stat-n">{stats.total_tasks}</span><span>Tasks</span></div>
          <div className="stat-box"><span className="stat-n meta-green">{stats.tasks_done}</span><span>Done</span></div>
        </div>
      )}

      <div className="memory-tabs">
        <button className={`mem-tab ${tab==='list'?'active':''}`} onClick={()=>setTab('list')}>📋 Projects</button>
        <button className={`mem-tab ${tab==='create'?'active':''}`} onClick={()=>setTab('create')}>＋ New</button>
        {selected && <button className={`mem-tab ${tab==='detail'?'active':''}`} onClick={()=>setTab('detail')}>📂 {selected.name?.slice(0,16)}</button>}
      </div>

      <div className="panel-body">
        {/* PROJECT LIST */}
        {tab === 'list' && (
          loading ? <div className="memory-empty">Loading…</div>
          : projects.length === 0 ? <div className="memory-empty">No projects yet — create one!</div>
          : (
            <div className="conv-list">
              {projects.map(p => (
                <div key={p.project_id} className="conv-item" onClick={() => openProject(p)}>
                  <div className="conv-header">
                    <span className="conv-title">{p.name}</span>
                    <span className="mem-tag" style={{color:STATUS_COLORS[p.status]||'#888'}}>{p.status}</span>
                    <span className="conv-count">{p.task_count} tasks</span>
                    <button className="del-btn" onClick={e=>{e.stopPropagation();handleDeleteProject(p.project_id)}}>✕</button>
                  </div>
                  <div className="conv-meta">
                    {p.tech_stack?.slice(0,4).map(t=><span key={t} className="mem-tag">{t}</span>)}
                  </div>
                  {p.description && <p className="conv-summary">{p.description.slice(0,100)}</p>}
                </div>
              ))}
            </div>
          )
        )}

        {/* CREATE PROJECT */}
        {tab === 'create' && (
          <div>
            <div className="form-field">
              <label className="form-label">Project name *</label>
              <input className="panel-input" placeholder="My Awesome Project"
                value={newProj.name} onChange={e=>setNewProj(p=>({...p,name:e.target.value}))}/>
            </div>
            <div className="form-field">
              <label className="form-label">Description</label>
              <textarea className="panel-textarea" rows={2} placeholder="What is this project about?"
                value={newProj.description} onChange={e=>setNewProj(p=>({...p,description:e.target.value}))}/>
            </div>
            <div className="form-field">
              <label className="form-label">Tech Stack</label>
              <div className="input-row">
                <input className="panel-input" placeholder="e.g. React, Python, FastAPI"
                  value={techInput} onChange={e=>setTechInput(e.target.value)}
                  onKeyDown={e=>e.key==='Enter'&&addTech()}/>
                <button className="btn-sm" onClick={addTech}>Add</button>
              </div>
              <div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:4}}>
                {newProj.tech_stack.map(t=>(
                  <span key={t} className="mem-tag" style={{cursor:'pointer'}}
                    onClick={()=>setNewProj(p=>({...p,tech_stack:p.tech_stack.filter(x=>x!==t)}))}>
                    {t} ✕
                  </span>
                ))}
              </div>
            </div>
            <div className="form-field">
              <label className="form-label">AI Context (injected into every AI prompt for this project)</label>
              <textarea className="panel-textarea" rows={2}
                placeholder="e.g. 'This is a fintech app. Use TypeScript. Prefer functional patterns.'"
                value={newProj.ai_context} onChange={e=>setNewProj(p=>({...p,ai_context:e.target.value}))}/>
            </div>
            <button className="btn-run" onClick={handleCreateProject} disabled={loading||!newProj.name.trim()}>
              {loading?<span className="spinner-sm"/>:'📁 Create Project'}
            </button>
          </div>
        )}

        {/* PROJECT DETAIL */}
        {tab === 'detail' && selected && (
          <div>
            <div className="conv-toolbar">
              <span className="conv-title">{selected.name}</span>
              <span className="mem-tag" style={{color:STATUS_COLORS[selected.status]||'#888'}}>{selected.status}</span>
              {selected.tech_stack?.slice(0,3).map(t=><span key={t} className="mem-tag">{t}</span>)}
            </div>

            <div className="memory-tabs" style={{marginBottom:12}}>
              {['tasks','notes','files'].map(dt=>(
                <button key={dt} className={`mem-tab ${detailTab===dt?'active':''}`}
                  onClick={()=>setDetailTab(dt)}>
                  {dt==='tasks'?`✅ Tasks (${tasks.length})`:dt==='notes'?`📝 Notes (${notes.length})`:`📎 Files (${files.length})`}
                </button>
              ))}
            </div>

            {/* TASKS */}
            {detailTab === 'tasks' && (
              <div>
                <div className="input-row" style={{marginBottom:8}}>
                  <input className="panel-input" placeholder="New task…"
                    value={newTask.title} onChange={e=>setNewTask(t=>({...t,title:e.target.value}))}
                    onKeyDown={e=>e.key==='Enter'&&handleCreateTask()}/>
                  <select className="panel-select" value={newTask.priority}
                    onChange={e=>setNewTask(t=>({...t,priority:+e.target.value}))}>
                    {[1,2,3,4,5].map(n=><option key={n} value={n}>{PRIORITY_LABELS[n]}</option>)}
                  </select>
                  <button className="btn-sm" onClick={handleCreateTask}>Add</button>
                </div>
                {['in_progress','todo','blocked','done'].map(status => {
                  const grp = tasksByStatus(status)
                  if (!grp.length && status !== 'todo') return null
                  return (
                    <div key={status} style={{marginBottom:12}}>
                      <div className="section-title" style={{marginBottom:6}}>
                        {status==='todo'?'📋 To Do':status==='in_progress'?'⚡ In Progress':status==='blocked'?'🚫 Blocked':'✅ Done'}
                        ({grp.length})
                      </div>
                      {grp.map(t => (
                        <div key={t.task_id} className="task-item">
                          <div style={{display:'flex',alignItems:'center',gap:8}}>
                            <select className="task-status-sel" value={t.status}
                              onChange={e=>handleUpdateTaskStatus(t.task_id,e.target.value)}>
                              {['todo','in_progress','done','blocked'].map(s=><option key={s} value={s}>{s}</option>)}
                            </select>
                            <span className="task-title" style={{textDecoration:t.status==='done'?'line-through':'none'}}>
                              {t.title}
                            </span>
                            <span style={{fontSize:10,color:'#888'}}>{PRIORITY_LABELS[t.priority]}</span>
                            <button className="del-btn" onClick={()=>handleDeleteTask(t.task_id)}>✕</button>
                          </div>
                          {t.description && <p className="task-desc">{t.description}</p>}
                        </div>
                      ))}
                    </div>
                  )
                })}
              </div>
            )}

            {/* NOTES */}
            {detailTab === 'notes' && (
              <div>
                <div className="form-field">
                  <input className="panel-input" placeholder="Note title"
                    value={newNote.title} onChange={e=>setNewNote(n=>({...n,title:e.target.value}))}/>
                  <textarea className="panel-textarea" rows={3} placeholder="Note content…" style={{marginTop:6}}
                    value={newNote.content} onChange={e=>setNewNote(n=>({...n,content:e.target.value}))}/>
                  <button className="btn-sm" style={{marginTop:6}} onClick={handleCreateNote}>Add Note</button>
                </div>
                {notes.map(n=>(
                  <div key={n.note_id} className="skill-card" style={{marginBottom:6}}>
                    <div className="skill-header"><span className="skill-name">{n.title}</span></div>
                    <p className="skill-desc">{n.content.slice(0,200)}</p>
                  </div>
                ))}
              </div>
            )}

            {/* FILES */}
            {detailTab === 'files' && (
              <div>
                <button className="btn-run" onClick={()=>fileRef.current?.click()}>
                  ⬆ Upload File
                </button>
                <input ref={fileRef} type="file" hidden onChange={handleFileUpload}/>
                {files.map(f=>(
                  <div key={f.name} className="skill-card" style={{marginBottom:4}}>
                    <div className="skill-header">
                      <span>📎</span>
                      <span className="skill-name">{f.name}</span>
                      <span className="skill-uses">{(f.size/1024).toFixed(1)}KB</span>
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
