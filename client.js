// src/api/client.js — Synapse v3, multi-platform (Web / Electron / Android)

const IS_ELECTRON = typeof window !== 'undefined' && window.synapse?.isElectron === true
const IS_ANDROID  = (typeof __IS_ANDROID__ !== 'undefined') ? __IS_ANDROID__ : false

function getDefaultBase() {
  if (IS_ELECTRON) return 'http://127.0.0.1:8000'
  if (IS_ANDROID)  return localStorage.getItem('synapse_backend_url') || 'http://192.168.1.100:8000'
  return (typeof import_meta_env_VITE_API_URL !== 'undefined')
    ? import_meta_env_VITE_API_URL
    : 'http://localhost:8000'
}

let BASE = (() => {
  try {
    if (IS_ELECTRON) return 'http://127.0.0.1:8000'
    if (IS_ANDROID)  return localStorage.getItem('synapse_backend_url') || 'http://192.168.1.100:8000'
    return import.meta.env.VITE_API_URL || 'http://localhost:8000'
  } catch { return 'http://localhost:8000' }
})()

export function setBackendUrl(url) {
  BASE = url.replace(/\/$/, '')
  try { localStorage.setItem('synapse_backend_url', BASE) } catch {}
}
export function getBackendUrl() { return BASE }

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
}

function sseStream(url, body, onChunk, onDone, onError) {
  const ctrl = new AbortController()
  fetch(`${BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  }).then(async (res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.chunk)                  onChunk(data.chunk)
          if (data.type === 'agent_role')  onChunk(`[AGENT:${data.role}]`)
          if (data.type === 'meta_route')  onChunk(`[META:${data.strategy}:${data.complexity || ''}]`)
          if (data.type === 'done')        onDone(data)
        } catch (_) {}
      }
    }
    onDone({})
  }).catch((e) => { if (e.name !== 'AbortError') onError(e) })
  return () => ctrl.abort()
}

export const apiClient = {
  isElectron: IS_ELECTRON,
  isAndroid:  IS_ANDROID,
  getBackendUrl, setBackendUrl,
  health:       () => apiFetch('/health'),
  systemStatus: () => apiFetch('/system/status'),
  evolution:    (limit = 50) => apiFetch(`/evolution?limit=${limit}`),
  chatStream: (message, sessionId, useAgent, onChunk, onDone, onError) =>
    sseStream('/chat', { message, session_id: sessionId, use_agent: useAgent, stream: true }, onChunk, onDone, onError),
  chat: (message, sessionId, useAgent = true) =>
    apiFetch('/chat', { method: 'POST', body: JSON.stringify({ message, session_id: sessionId, use_agent: useAgent, stream: false }) }),
  reason: (task, strategy = 'auto', context = '', role = 'general') =>
    apiFetch('/reasoning/think', { method: 'POST', body: JSON.stringify({ task, strategy, context, role }) }),
  critique:  (task, context = '') =>
    apiFetch('/reasoning/critique', { method: 'POST', body: JSON.stringify({ task, context }) }),
  decompose: (task) =>
    apiFetch('/reasoning/decompose', { method: 'POST', body: JSON.stringify({ task }) }),
  reasonStream: (task, strategy, context, onChunk, onDone, onError) =>
    sseStream('/reasoning/think/stream', { task, strategy, context }, onChunk, onDone, onError),
  streamPlan: (goal, context = '', onChunk, onDone, onError) =>
    sseStream('/plan', { goal, context, stream: true }, onChunk, onDone, onError),
  plan: (goal, context = '') =>
    apiFetch('/plan', { method: 'POST', body: JSON.stringify({ goal, context, stream: false }) }),
  improve: ({ code, goal, language, mode, max_iterations }) =>
    apiFetch('/improve', { method: 'POST', body: JSON.stringify({ code, goal, language, mode, max_iterations }) }),
  detectGap: (user_request, failure_reason = '') =>
    apiFetch('/capability/detect', { method: 'POST', body: JSON.stringify({ user_request, failure_reason }) }),
  autoExpand: (user_request, failure_reason = '') =>
    apiFetch('/capability/expand', { method: 'POST', body: JSON.stringify({ user_request, failure_reason }) }),
  createTool: (data) =>
    apiFetch('/capability/create', { method: 'POST', body: JSON.stringify(data) }),
  listCapabilities: () => apiFetch('/capability/list'),
  deleteCapability: (tool_name) =>
    apiFetch(`/capability/${encodeURIComponent(tool_name)}`, { method: 'DELETE' }),
  runTool: (tool, params) =>
    apiFetch('/tools/run', { method: 'POST', body: JSON.stringify({ tool, params }) }),
  listTools: () => apiFetch('/tools/list'),
  listSkills: (skill_type = null, limit = 50) => {
    const qs = skill_type ? `?skill_type=${encodeURIComponent(skill_type)}&limit=${limit}` : `?limit=${limit}`
    return apiFetch(`/skills/list${qs}`)
  },
  searchSkills: (query, n = 10) =>
    apiFetch('/skills/search', { method: 'POST', body: JSON.stringify({ query, n_results: n }) }),
  distillKnowledge: (topic, session_id = 'default') =>
    apiFetch('/skills/distill', { method: 'POST', body: JSON.stringify({ topic, session_id }) }),
  getKnowledge: (topic = null) => {
    const qs = topic ? `?topic=${encodeURIComponent(topic)}` : ''
    return apiFetch(`/skills/knowledge${qs}`)
  },
  deleteSkill: (skill_id) =>
    apiFetch(`/skills/${encodeURIComponent(skill_id)}`, { method: 'DELETE' }),
  searchMemory: (query, n = 5) =>
    apiFetch('/memory/search', { method: 'POST', body: JSON.stringify({ query, n_results: n }) }),
  listMemory: (session_id = 'default', limit = 20) =>
    apiFetch(`/memory/list?session_id=${encodeURIComponent(session_id)}&limit=${limit}`),
  clearMemory: (session_id) =>
    apiFetch(`/memory/clear?session_id=${encodeURIComponent(session_id)}`, { method: 'DELETE' }),
  healingStatus: () => apiFetch('/healing/status'),
  healingLog:    (limit = 20) => apiFetch(`/healing/log?limit=${limit}`),
  forceRepair:   (component) =>
    apiFetch(`/healing/repair/${encodeURIComponent(component)}`, { method: 'POST' }),
}

// ── RAG ────────────────────────────────────────────────────────
export const ragClient = {
  upload:   (file) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(`${BASE}/rag/upload`, { method:'POST', body:fd }).then(r=>r.json())
  },
  query:    (question, doc_id, n_chunks) =>
    apiFetch('/rag/query',{method:'POST',body:JSON.stringify({question,doc_id,n_chunks,stream:false})}),
  queryStream: (question, doc_id, n_chunks, onChunk, onDone, onError) =>
    sseStream('/rag/query',{question,doc_id,n_chunks,stream:true},onChunk,onDone,onError),
  list:     () => apiFetch('/rag/docs'),
  summarise:(doc_id) => apiFetch(`/rag/summarise/${doc_id}`,{method:'POST'}),
  delete:   (doc_id) => apiFetch(`/rag/docs/${doc_id}`,{method:'DELETE'}),
}

// ── Web Search ──────────────────────────────────────────────────
export const searchClient = {
  search:       (query, n, summarise) => apiFetch('/search',{method:'POST',body:JSON.stringify({query,n,summarise,stream:false})}),
  searchStream: (query, n, onChunk, onDone, onError) =>
    sseStream('/search',{query,n,summarise:true,stream:true},onChunk,onDone,onError),
  fetch:        (url) => apiFetch('/search/fetch',{method:'POST',body:JSON.stringify({url})}),
}

// ── Vision ──────────────────────────────────────────────────────
export const visionClient = {
  analyse:     (image_b64, task, question) => apiFetch('/vision/analyse',{method:'POST',body:JSON.stringify({image_b64,task,question})}),
  analyseStream: (image_b64, task, question, onChunk, onDone, onError) =>
    sseStream('/vision/analyse/stream',{image_b64,task,question},onChunk,onDone,onError),
  analyseUrl:  (url, task, question) => apiFetch('/vision/url',{method:'POST',body:JSON.stringify({url,task,question})}),
  tasks:       () => apiFetch('/vision/tasks'),
}

// ── Model Router ────────────────────────────────────────────────
export const routerClient = {
  models:      () => apiFetch('/router/models'),
  discover:    () => apiFetch('/router/discover',{method:'POST'}),
  benchmark:   (model) => apiFetch(`/router/benchmark/${encodeURIComponent(model)}`,{method:'POST'}),
  benchmarkAll:() => apiFetch('/router/benchmark-all',{method:'POST'}),
  route:       (task) => apiFetch(`/router/route/${task}`),
}

// ── Benchmark Engine ────────────────────────────────────────────
export const benchClient = {
  run:     (suite, model, onChunk, onDone, onError) =>
    sseStream('/benchmark/run',{suite,model,stream:true},onChunk,onDone,onError),
  runs:    (limit=10) => apiFetch(`/benchmark/runs?limit=${limit}`),
  getrun:  (id) => apiFetch(`/benchmark/runs/${id}`),
  suites:  () => apiFetch('/benchmark/suites'),
}

// Attach to apiClient for convenience
Object.assign(apiClient, {
  uploadRAGDoc:  ragClient.upload,
  ragQueryStream:ragClient.queryStream,
  listRAGDocs:   ragClient.list,
  ragSummarise:  ragClient.summarise,
  deleteRAGDoc:  ragClient.delete,
  searchStream:  searchClient.searchStream,
  visionStream:  (b64,task,q,onC,onD,onE) => visionClient.analyseStream(b64,task,q,onC,onD,onE),
  visionTasks:   visionClient.tasks,
  benchmarkRun:  (suite,model,onC,onD,onE) => benchClient.run(suite,model,onC,onD,onE),
  benchmarkRuns: benchClient.runs,
  benchmarkSuites:benchClient.suites,
  routerModels:  routerClient.models,
})

// ── Voice (v5) ──────────────────────────────────────────────────
Object.assign(apiClient, {
  voiceStatus:    () => apiFetch('/voice/status'),
  voiceVoices:    () => apiFetch('/voice/voices'),
  voiceTranscribe:(file, language) => {
    const fd = new FormData(); fd.append('file', file); fd.append('language', language)
    return fetch(`${BASE}/voice/transcribe`,{method:'POST',body:fd}).then(r=>r.json())
  },
  voiceTTS: (text, voice, speed) =>
    fetch(`${BASE}/voice/tts`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text,voice,speed})}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.blob()}),
  voiceTTSb64: (text, voice, speed) =>
    apiFetch('/voice/tts/b64',{method:'POST',body:JSON.stringify({text,voice,speed})}),

  // ── Collab (v5) ─────────────────────────────────────────────────
  collabRun: (topic, mode, agents, rounds, onChunk, onDone, onError) =>
    sseStream('/collab/run',{topic,mode,agents,rounds,stream:true},onChunk,onDone,onError),
  collabRoles: () => apiFetch('/collab/roles'),
  collabModes: () => apiFetch('/collab/modes'),

  // ── Knowledge Graph (v5) ─────────────────────────────────────────
  kgExtract:  (text, source='') => apiFetch('/kg/extract',{method:'POST',body:JSON.stringify({text,source})}),
  kgQuery:    (question, depth=2) => apiFetch('/kg/query',{method:'POST',body:JSON.stringify({question,depth})}),
  kgSearch:   (q, entity_type='', limit=20) => apiFetch(`/kg/search?q=${encodeURIComponent(q)}&entity_type=${entity_type}&limit=${limit}`),
  kgViz:      (limit=100) => apiFetch(`/kg/viz?limit=${limit}`),
  kgStats:    () => apiFetch('/kg/stats'),
  kgAddEntity:(name, type, desc) => apiFetch('/kg/entity',{method:'POST',body:JSON.stringify({name,entity_type:type,description:desc})}),
  kgAddRelation:(from_id,relation,to_id) => apiFetch('/kg/relation',{method:'POST',body:JSON.stringify({from_id,relation,to_id})}),
  kgPath:     (from_id,to_id) => apiFetch('/kg/path',{method:'POST',body:JSON.stringify({from_id,to_id})}),
  kgDelete:   (id) => apiFetch(`/kg/entity/${encodeURIComponent(id)}`,{method:'DELETE'}),

  // ── Conversations (v5) ───────────────────────────────────────────
  listConversations: (limit=50, offset=0, search='') =>
    apiFetch(`/conversations?limit=${limit}&offset=${offset}&search=${encodeURIComponent(search)}`),
  getConversation:   (id) => apiFetch(`/conversations/${id}`),
  getConversationMessages: (id, limit=100) => apiFetch(`/conversations/${id}/messages?limit=${limit}`),
  summariseConversation:   (id) => apiFetch(`/conversations/${id}/summarise`,{method:'POST'}),
  exportConversation:(id, format='markdown') =>
    fetch(`${BASE}/conversations/export`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_id:id,format})}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.blob()}),
  searchConversations: (query, limit=20) =>
    apiFetch('/conversations/search',{method:'POST',body:JSON.stringify({query,limit})}),
  convAnalytics:     () => apiFetch('/conversations/analytics/summary'),
  deleteConversation:(id) => apiFetch(`/conversations/${id}`,{method:'DELETE'}),
})

// ── v6 API methods ──────────────────────────────────────────────
Object.assign(apiClient, {
  // Plugins
  installPlugin:  (package_, description='', auto_generate_tools=true) =>
    apiFetch('/plugins/install',{method:'POST',body:JSON.stringify({package:package_,description,auto_generate_tools})}),
  removePlugin:   (pkg) => apiFetch(`/plugins/${encodeURIComponent(pkg)}`,{method:'DELETE'}),
  listPlugins:    () => apiFetch('/plugins/list'),
  allowedPlugins: () => apiFetch('/plugins/allowed'),
  checkPlugin:    (pkg) => apiFetch(`/plugins/check/${encodeURIComponent(pkg)}`,{method:'POST'}),

  // Deep Research
  researchStream: (topic, depth='standard', onChunk, onDone, onError) =>
    sseStream('/research',{topic,depth,stream:true,use_memory:true},onChunk,onDone,onError),
  research:       (topic, depth='standard') =>
    apiFetch('/research',{method:'POST',body:JSON.stringify({topic,depth,stream:false})}),

  // Projects
  createProject:  (data) => apiFetch('/projects',{method:'POST',body:JSON.stringify(data)}),
  listProjects:   (status='') => apiFetch(`/projects${status?`?status=${status}`:''}`),
  getProject:     (id) => apiFetch(`/projects/${id}`),
  updateProject:  (id, data) => apiFetch(`/projects/${id}`,{method:'PATCH',body:JSON.stringify(data)}),
  deleteProject:  (id) => apiFetch(`/projects/${id}`,{method:'DELETE'}),
  createTask:     (pid, data) => apiFetch(`/projects/${pid}/tasks`,{method:'POST',body:JSON.stringify(data)}),
  listTasks:      (pid, status='') => apiFetch(`/projects/${pid}/tasks${status?`?status=${status}`:''}`),
  updateTask:     (pid, tid, data) => apiFetch(`/projects/${pid}/tasks/${tid}`,{method:'PATCH',body:JSON.stringify(data)}),
  deleteTask:     (pid, tid) => apiFetch(`/projects/${pid}/tasks/${tid}`,{method:'DELETE'}),
  createProjectNote:(pid, data) => apiFetch(`/projects/${pid}/notes`,{method:'POST',body:JSON.stringify(data)}),
  listProjectNotes: (pid) => apiFetch(`/projects/${pid}/notes`),
  uploadProjectFile:(pid, file) => {
    const fd=new FormData(); fd.append('file',file)
    return fetch(`${BASE}/projects/${pid}/files`,{method:'POST',body:fd}).then(r=>r.json())
  },
  listProjectFiles: (pid) => apiFetch(`/projects/${pid}/files`),
  projectContext:   (pid) => apiFetch(`/projects/${pid}/context`),

  // Prompts
  createPrompt:   (data) => apiFetch('/prompts',{method:'POST',body:JSON.stringify(data)}),
  listPrompts:    (category='', search='', limit=50) =>
    apiFetch(`/prompts?category=${encodeURIComponent(category)}&search=${encodeURIComponent(search)}&limit=${limit}`),
  promptCategories:() => apiFetch('/prompts/categories'),
  getPrompt:      (id) => apiFetch(`/prompts/${id}`),
  generatePrompt: (data) => apiFetch('/prompts/generate',{method:'POST',body:JSON.stringify(data)}),
  improvePrompt:  (id) => apiFetch(`/prompts/${id}/improve`,{method:'POST'}),
  applyPrompt:    (template_id, variables) =>
    apiFetch('/prompts/apply',{method:'POST',body:JSON.stringify({template_id,variables})}),
  ratePrompt:     (id, rating) => apiFetch(`/prompts/${id}/rate?rating=${rating}`,{method:'POST'}),
  deletePrompt:   (id) => apiFetch(`/prompts/${id}`,{method:'DELETE'}),
})

// ── v7 Intelligence API ─────────────────────────────────────────
Object.assign(apiClient, {
  // Hypothesis Engine
  hypothesisStream:   (observation, max_iter, onChunk, onDone, onError) =>
    sseStream('/hypothesis/generate', {observation, max_iterations:max_iter, stream:true}, onChunk, onDone, onError),
  hypothesisGenerate: (observation, n=3) =>
    apiFetch('/hypothesis/generate', {method:'POST', body:JSON.stringify({observation,n,stream:false})}),
  causalAnalysis:     (situation) => apiFetch('/hypothesis/causal', {method:'POST', body:JSON.stringify({situation})}),
  abductiveInference: (observations) => apiFetch('/hypothesis/abductive', {method:'POST', body:JSON.stringify({observations})}),
  analyzeArgument:    (argument) => apiFetch('/hypothesis/argument', {method:'POST', body:JSON.stringify({argument})}),
  thinkExplicitly:    (question, context, onChunk, onDone, onError) =>
    sseStream('/hypothesis/think-explicitly', {question, context, stream:true}, onChunk, onDone, onError),
  autoTest:           (observation) => apiFetch('/hypothesis/auto-test', {method:'POST', body:JSON.stringify({observation})}),

  // Uncertainty Engine
  uncertaintyAssess:       (question) => apiFetch('/uncertainty/assess', {method:'POST', body:JSON.stringify({question})}),
  uncertaintyAnswerStream: (question, context, onChunk, onDone, onError) =>
    sseStream('/uncertainty/answer', {question, context, stream:true}, onChunk, onDone, onError),
  socraticCheck:           (request) => apiFetch('/uncertainty/socratic', {method:'POST', body:JSON.stringify({request})}),
  selfDoubt:               (question, answer) => apiFetch('/uncertainty/self-doubt', {method:'POST', body:JSON.stringify({question, answer})}),
  uncertaintyStats:        () => apiFetch('/uncertainty/stats'),

  // Memory Consolidation
  runConsolidation:      (session_id='default', aggressive=false) =>
    apiFetch('/consolidation/run', {method:'POST', body:JSON.stringify({session_id, aggressive})}),
  consolidateAll:        () => apiFetch('/consolidation/run-all', {method:'POST'}),
  consolidationHistory:  (limit=10) => apiFetch(`/consolidation/history?limit=${limit}`),

  // Intelligence Monitor
  intelStats:      () => apiFetch('/intelligence/stats'),
  intelProfile:    (days=7) => apiFetch(`/intelligence/profile?days=${days}`),
  intelGrowth:     (days=30, bucket_hours=24) => apiFetch(`/intelligence/growth?days=${days}&bucket_hours=${bucket_hours}`),
  intelDimensions: () => apiFetch('/intelligence/dimensions'),
  intelMilestones: () => apiFetch('/intelligence/milestones'),
  intelEvaluate:   (task, response, agent_role='general') =>
    apiFetch('/intelligence/evaluate', {method:'POST', body:JSON.stringify({task, response, agent_role})}),
})
