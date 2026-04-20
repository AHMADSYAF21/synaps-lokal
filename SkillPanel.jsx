import { useState, useEffect } from "react"
import { apiClient } from "../api/client"

export default function SkillPanel() {
  const [skills, setSkills] = useState([])
  const [knowledge, setKnowledge] = useState([])
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState("skills")
  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [distillTopic, setDistillTopic] = useState("")
  const [distillResult, setDistillResult] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const [sk, kn] = await Promise.all([
        apiClient.listSkills(),
        apiClient.getKnowledge(),
      ])
      setSkills(sk.skills || [])
      setStats(sk.stats)
      setKnowledge(kn.knowledge || [])
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  async function handleSearch() {
    if (!search.trim()) return
    const r = await apiClient.searchSkills(search, 10)
    setSearchResults(r.skills || [])
    setTab("search")
  }

  async function handleDistill() {
    if (!distillTopic.trim()) return
    setLoading(true)
    const r = await apiClient.distillKnowledge(distillTopic)
    setDistillResult(r)
    await load()
    setLoading(false)
  }

  async function handleDelete(id) {
    await apiClient.deleteSkill(id)
    setSkills(s => s.filter(x => x.id !== id))
  }

  const typeColors = {
    code_pattern: "#10b981",
    reasoning_pattern: "#6366f1",
    domain_knowledge: "#06b6d4",
    workflow: "#f59e0b",
  }

  const display = tab === "search" ? searchResults : tab === "knowledge" ? [] : skills

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>◆ Skill Library</h2>
        <p className="panel-sub">Patterns learned from successful interactions — auto-injected into future prompts</p>
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-box"><span className="stat-n">{stats.total_skills}</span><span>Skills</span></div>
          <div className="stat-box"><span className="stat-n">{stats.knowledge_topics}</span><span>Knowledge</span></div>
          <div className="stat-box"><span className="stat-n">{stats.total_interactions_logged}</span><span>Interactions</span></div>
          {stats.top_skills?.slice(0,1).map(s => (
            <div key={s.name} className="stat-box"><span className="stat-n">{s.uses}×</span><span>{s.name}</span></div>
          ))}
        </div>
      )}

      <div className="panel-body">
        {/* Search + Distill */}
        <div className="double-row">
          <div className="input-row flex1">
            <input className="panel-input" placeholder="Search skills semantically…"
              value={search} onChange={e=>setSearch(e.target.value)}
              onKeyDown={e=>e.key==="Enter"&&handleSearch()} />
            <button className="btn-sm" onClick={handleSearch}>Search</button>
            {tab==="search" && <button className="btn-sm-ghost" onClick={()=>setTab("skills")}>← Back</button>}
          </div>
          <div className="input-row flex1">
            <input className="panel-input" placeholder="Distill knowledge on topic…"
              value={distillTopic} onChange={e=>setDistillTopic(e.target.value)}
              onKeyDown={e=>e.key==="Enter"&&handleDistill()} />
            <button className="btn-sm btn-amber" onClick={handleDistill} disabled={loading}>Distill</button>
          </div>
        </div>

        {/* Distill Result */}
        {distillResult?.success && distillResult.knowledge && (
          <div className="distill-card">
            <div className="distill-title">◆ Knowledge Distilled</div>
            {Object.entries(distillResult.knowledge).map(([k,v]) => (
              <div key={k} className="distill-section">
                <span className="distill-key">{k}:</span>
                <ul>{(Array.isArray(v)?v:[v]).slice(0,4).map((i,idx)=><li key={idx}>{i}</li>)}</ul>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="memory-tabs">
          <button className={`mem-tab ${tab==="skills"?"active":""}`} onClick={()=>setTab("skills")}>
            Skills ({skills.length})
          </button>
          <button className={`mem-tab ${tab==="knowledge"?"active":""}`} onClick={()=>setTab("knowledge")}>
            Knowledge ({knowledge.length})
          </button>
          <button className={`mem-tab ${tab==="search"?"active":""}`} onClick={()=>setTab("search")}>
            Results ({searchResults.length})
          </button>
        </div>

        {/* Skill List */}
        {tab !== "knowledge" && (
          loading ? <div className="memory-empty">Loading…</div>
          : display.length === 0 ? (
            <div className="memory-empty">
              {tab==="search" ? "No skills matched" : "No skills yet — start chatting to build the library"}
            </div>
          ) : (
            <div className="skill-list">
              {display.map((s,i) => (
                <div key={s.id||i} className="skill-card">
                  <div className="skill-header">
                    <span className="skill-type-dot" style={{background: typeColors[s.skill_type]||"#888"}}/>
                    <span className="skill-name">{s.name}</span>
                    <span className="skill-score">{(s.confidence*100).toFixed(0)}%</span>
                    <span className="skill-uses">{s.use_count}× used</span>
                    {s.id && <button className="del-btn" onClick={()=>handleDelete(s.id)}>✕</button>}
                  </div>
                  <p className="skill-desc">{s.description}</p>
                  {s.reusable_pattern && (
                    <div className="skill-pattern">
                      <span className="pattern-label">Pattern:</span> {s.reusable_pattern.slice(0,150)}
                    </div>
                  )}
                  {s.tags?.length > 0 && (
                    <div className="skill-tags">{s.tags.slice(0,5).map(t=><span key={t} className="mem-tag">{t}</span>)}</div>
                  )}
                </div>
              ))}
            </div>
          )
        )}

        {/* Knowledge List */}
        {tab === "knowledge" && (
          knowledge.length === 0 ? (
            <div className="memory-empty">No knowledge distilled yet</div>
          ) : (
            <div className="skill-list">
              {knowledge.map((k,i) => (
                <div key={k.id||i} className="skill-card">
                  <div className="skill-header">
                    <span className="skill-name">◎ {k.topic}</span>
                    <span className="skill-uses">{k.interaction_count} interactions</span>
                  </div>
                  {k.facts?.length>0 && <div className="distill-section"><b>Facts:</b> {k.facts.slice(0,2).join("; ")}</div>}
                  {k.rules?.length>0 && <div className="distill-section"><b>Rules:</b> {k.rules.slice(0,2).join("; ")}</div>}
                  {k.best_practices?.length>0 && <div className="distill-section"><b>Best practices:</b> {k.best_practices.slice(0,2).join("; ")}</div>}
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  )
}
