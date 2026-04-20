import { useState, useEffect } from 'react'
import Chat from './components/Chat'
import AgentStatus from './components/AgentStatus'
import MemoryPanel from './components/MemoryPanel'
import SkillPanel from './components/SkillPanel'
import CapabilityPanel from './components/CapabilityPanel'
import SystemPanel from './components/SystemPanel'
import RAGPanel from './components/RAGPanel'
import SearchPanel from './components/SearchPanel'
import VisionPanel from './components/VisionPanel'
import BenchmarkPanel from './components/BenchmarkPanel'
import VoicePanel from './components/VoicePanel'
import CollabPanel from './components/CollabPanel'
import KnowledgeGraphPanel from './components/KnowledgeGraphPanel'
import ConversationsPanel from './components/ConversationsPanel'
import ResearchPanel from './components/ResearchPanel'
import ProjectsPanel from './components/ProjectsPanel'
import PromptsPanel from './components/PromptsPanel'
import PluginsPanel from './components/PluginsPanel'
import IntelligencePanel from './components/IntelligencePanel'
import AndroidSettings from './components/AndroidSettings'
import { apiClient } from './api/client'
import './App.css'

const IS_ELECTRON = typeof window!=='undefined' && window.synapse?.isElectron===true
const IS_ANDROID  = (typeof __IS_ANDROID__!=='undefined') ? __IS_ANDROID__ : false

const NAV = [
  // Main
  { id:'chat',       icon:'⬡',  label:'Chat',        group:'main'    },
  { id:'voice',      icon:'🎙', label:'Voice',       group:'main'    },
  { id:'projects',   icon:'📁', label:'Projects',    group:'main'    },
  // Intelligence
  { id:'research',   icon:'🔬', label:'Research',    group:'intel'   },
  { id:'rag',        icon:'📄', label:'Documents',   group:'intel'   },
  { id:'search',     icon:'🌐', label:'Search',      group:'intel'   },
  { id:'vision',     icon:'👁', label:'Vision',      group:'intel'   },
  { id:'collab',     icon:'🤝', label:'Collaborate', group:'intel'   },
  { id:'kg',         icon:'🕸', label:'Knowledge',   group:'intel'   },
  // Build
  { id:'plan',       icon:'◈',  label:'Planner',     group:'build'   },
  { id:'improve',    icon:'⟳',  label:'Improve',     group:'build'   },
  { id:'prompts',    icon:'📜', label:'Prompts',     group:'build'   },
  { id:'plugins',    icon:'🔌', label:'Plugins',     group:'build'   },
  // Data
  { id:'memory',     icon:'◎',  label:'Memory',      group:'data'    },
  { id:'skills',     icon:'◆',  label:'Skills',      group:'data'    },
  { id:'convs',      icon:'💬', label:'History',     group:'data'    },
  { id:'capability', icon:'⊕',  label:'Capabilities',group:'data'   },
  { id:'benchmark',  icon:'📊', label:'Benchmark',   group:'data'    },
  { id:'intelligence',icon:'🧠', label:'Intelligence',group:'system'  },
  { id:'system',     icon:'⬟',  label:'System',      group:'system'  },
]

const MOBILE_NAV = ['chat','voice','research','projects','system']
const GROUPS = { main:'Main', intel:'Intelligence', build:'Build', data:'Data', system:'System' }

export default function App() {
  const [health,setHealth]=useState(null)
  const [panel,setPanel]=useState('chat')
  const [agentStatus,setAgentStatus]=useState({role:null,thinking:false})
  const [connected,setConnected]=useState(!IS_ANDROID)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)

  useEffect(()=>{
    if(!connected)return
    const load=()=>apiClient.health().then(setHealth).catch(()=>setHealth({status:'offline'}))
    load(); const t=setInterval(load,30000); return()=>clearInterval(t)
  },[connected])

  if(IS_ANDROID&&!connected)
    return <div className="app-root" style={{display:'block'}}>
      <AndroidSettings onConnected={()=>setConnected(true)}/>
    </div>

  const groupedNav = Object.entries(GROUPS).map(([gid,glabel])=>({
    gid, glabel, items: NAV.filter(n=>n.group===gid)
  }))

  return (
    <div className="app-root" style={{gridTemplateColumns:sidebarCollapsed?'48px 1fr':'220px 1fr'}}>
      {IS_ELECTRON&&(
        <div className="electron-titlebar" style={{gridColumn:'1/-1'}}>
          <span style={{color:'var(--accent)',fontSize:14}}>◈</span>
          <span className="titlebar-title">SYNAPSE LOCAL v6</span>
          <span className="titlebar-status" onClick={()=>window.synapse?.openBrowser()}>
            {health?.status==='ok'?'● ONLINE':'○ offline'}
          </span>
        </div>
      )}

      <aside className="sidebar" style={{overflow:sidebarCollapsed?'hidden':'auto'}}>
        {!sidebarCollapsed && (
          <>
            <div className="sidebar-brand">
              <span className="brand-icon">◈</span>
              <div><div className="brand-name">SYNAPSE</div><div className="brand-sub">LOCAL v6</div></div>
            </div>
            <div className="health-badge" data-status={health?.status||'loading'}>
              <span className="health-dot"/>
              <span>{health?.status==='ok'?'ONLINE':health?.status==='offline'?'OFFLINE':'…'}</span>
            </div>
          </>
        )}
        <nav className="sidebar-nav">
          {/* Collapse toggle */}
          <button className="nav-item" onClick={()=>setSidebarCollapsed(c=>!c)}
            style={{justifyContent:'center',minHeight:32}}>
            <span className="nav-icon">{sidebarCollapsed?'▶':'◀'}</span>
            {!sidebarCollapsed&&<span>Collapse</span>}
          </button>

          {groupedNav.map(({gid,glabel,items})=>(
            <div key={gid}>
              {!sidebarCollapsed&&<div className="nav-group-label">{glabel}</div>}
              {items.map(n=>(
                <button key={n.id} className={`nav-item ${panel===n.id?'active':''}`}
                  onClick={()=>setPanel(n.id)} title={n.label}>
                  <span className="nav-icon">{n.icon}</span>
                  {!sidebarCollapsed&&<span>{n.label}</span>}
                </button>
              ))}
            </div>
          ))}

          {IS_ANDROID&&(
            <button className="nav-item" onClick={()=>setConnected(false)} title="Server">
              <span className="nav-icon">⚙</span>
              {!sidebarCollapsed&&<span>Server</span>}
            </button>
          )}
        </nav>

        {!sidebarCollapsed&&<>
          <AgentStatus status={agentStatus}/>
          {health&&(
            <div className="sidebar-meta">
              <div className="meta-row"><span>Skills</span><span className="meta-val meta-accent">{health.skills?.total_skills??0}</span></div>
              <div className="meta-row"><span>Docs</span><span className="meta-val meta-cyan">{health.rag?.total_documents??0}</span></div>
              <div className="meta-row"><span>Projects</span><span className="meta-val meta-green">{health.projects?.total_projects??0}</span></div>
              <div className="meta-row"><span>Prompts</span><span className="meta-val">{health.prompts?.total??0}</span></div>
            </div>
          )}
        </>}
      </aside>

      <main className="main-area">
        {panel==='chat'       && <Chat onAgentStatus={setAgentStatus}/>}
        {panel==='voice'      && <VoicePanel/>}
        {panel==='projects'   && <ProjectsPanel/>}
        {panel==='research'   && <ResearchPanel/>}
        {panel==='rag'        && <RAGPanel/>}
        {panel==='search'     && <SearchPanel/>}
        {panel==='vision'     && <VisionPanel/>}
        {panel==='collab'     && <CollabPanel/>}
        {panel==='kg'         && <KnowledgeGraphPanel/>}
        {panel==='plan'       && <PlannerPanel/>}
        {panel==='improve'    && <ImprovePanel/>}
        {panel==='prompts'    && <PromptsPanel/>}
        {panel==='plugins'    && <PluginsPanel/>}
        {panel==='memory'     && <MemoryPanel/>}
        {panel==='skills'     && <SkillPanel/>}
        {panel==='convs'      && <ConversationsPanel/>}
        {panel==='capability' && <CapabilityPanel/>}
        {panel==='benchmark'  && <BenchmarkPanel/>}
        {panel==='intelligence' && <IntelligencePanel/>}
        {panel==='system'     && <SystemPanel health={health}/>}
      </main>

      <nav className="mobile-nav">
        {MOBILE_NAV.map(id=>{
          const n=NAV.find(x=>x.id===id)
          return n?(<button key={id} className={`mobile-nav-btn ${panel===id?'active':''}`} onClick={()=>setPanel(id)}>
            <span>{n.icon}</span><span>{n.label}</span></button>):null
        })}
      </nav>
    </div>
  )
}

function PlannerPanel(){
  const [goal,setGoal]=useState(''); const [output,setOutput]=useState(''); const [running,setRunning]=useState(false)
  const run=()=>{if(!goal.trim()||running)return;setRunning(true);setOutput('')
    apiClient.streamPlan(goal,'',c=>setOutput(p=>p+c),()=>setRunning(false),e=>{setOutput(p=>p+`\nERROR: ${e.message}`);setRunning(false)})}
  return(<div className="generic-panel"><div className="panel-header"><h2>◈ Multi-Step Planner</h2><p className="panel-sub">Decompose complex goals into ordered steps</p></div>
    <div className="panel-body"><div className="input-row">
      <textarea className="panel-textarea" rows={3} placeholder="Describe goal…" value={goal}
        onChange={e=>setGoal(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&e.ctrlKey)run()}}/>
      <button className="btn-run" onClick={run} disabled={running||!goal.trim()}>{running?<span className="spinner-sm"/>:'▶ Run'}</button>
    </div>{output&&<div className="output-block"><pre>{output}</pre></div>}</div></div>)
}

function ImprovePanel(){
  const [mode,setMode]=useState('improve'); const [code,setCode]=useState(''); const [goal,setGoal]=useState('')
  const [lang,setLang]=useState('python'); const [iters,setIters]=useState(3)
  const [result,setResult]=useState(null); const [running,setRunning]=useState(false)
  const run=async()=>{if(running)return;setRunning(true);setResult(null)
    try{const r=await apiClient.improve({code,goal,language:lang,mode,max_iterations:iters});setResult(r)}
    catch(e){setResult({success:false,error:e.message})}finally{setRunning(false)}}
  return(<div className="generic-panel"><div className="panel-header"><h2>⟳ Self-Improvement Loop</h2><p className="panel-sub">Generate → Execute → Critique → Refine</p></div>
    <div className="panel-body">
      <div className="control-row">
        <select className="panel-select" value={mode} onChange={e=>setMode(e.target.value)}>
          <option value="improve">Improve code</option><option value="generate">Generate from goal</option></select>
        <select className="panel-select" value={lang} onChange={e=>setLang(e.target.value)}>
          <option value="python">Python</option><option value="javascript">JavaScript</option></select>
        <select className="panel-select" value={iters} onChange={e=>setIters(+e.target.value)}>
          {[2,3,4,5,6,8].map(n=><option key={n} value={n}>{n} iterations</option>)}</select></div>
      {mode==='improve'&&<textarea className="panel-textarea code-ta" rows={8} placeholder="Paste code…" value={code} onChange={e=>setCode(e.target.value)}/>}
      <input className="panel-input" placeholder="Goal…" value={goal} onChange={e=>setGoal(e.target.value)}/>
      <button className="btn-run" onClick={run} disabled={running}>{running?<><span className="spinner-sm"/> Improving…</>:'⟳ Start'}</button>
      {result&&(<div className={`result-card ${result.success?'success':'warn'}`}>
        <div className="result-header"><span>{result.success?'✅':'⚠️'} {result.summary||result.error}</span>
          <span className="result-score">{result.best_score?.toFixed(1)}/10</span></div>
        {result.skill_learned&&<span className="skill-badge">◆ Skill learned</span>}
        {result.final_code&&<pre className="final-code">{result.final_code}</pre>}</div>)}
    </div></div>)
}
