"""
SYNAPSE LOCAL v7 — Intelligence-Upgraded AI Backend
New: Hypothesis Engine · Uncertainty Engine · Memory Consolidation
     Context Optimizer · Intelligence Monitor
"""
import asyncio, base64, json, logging, random, time
from contextlib import asynccontextmanager
from dataclasses import asdict
from fastapi import FastAPI, BackgroundTasks, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# All existing modules
from core.llm              import LLMService
from core.memory           import MemoryService
from core.tools            import ToolRegistry
from core.agents           import AgentOrchestrator
from core.reasoning        import ReasoningEngine
from core.capability_engine import CapabilityEngine
from core.skill_library    import SkillLibrary
from core.planner          import Planner
from core.self_heal        import SelfHealingMonitor
from core.self_improve_v2  import SelfImprovementV2
from core.meta_agent       import MetaAgent
from core.rag_engine       import RAGEngine
from core.web_search       import WebSearchEngine
from core.vision_engine    import VisionEngine
from core.model_router     import ModelRouter
from core.benchmark_engine import BenchmarkEngine
from core.voice_engine     import VoiceEngine
from core.collab_engine    import MultiAgentCollaboration
from core.knowledge_graph  import KnowledgeGraph
from core.conversation_manager import ConversationManager
from core.plugin_system    import PluginSystem
from core.deep_researcher  import DeepResearcher
from core.project_manager  import ProjectManager
from core.prompt_library   import PromptLibrary
# v7 intelligence upgrades
from core.hypothesis_engine    import HypothesisEngine
from core.uncertainty_engine   import UncertaintyEngine, asdict_report
from core.memory_consolidation import MemoryConsolidation
from core.context_optimizer    import ContextOptimizer
from core.intelligence_monitor import IntelligenceMonitor
from config import Config

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("synapse")

# ── Globals ───────────────────────────────────────────────────────
llm=memory=tools=orchestrator=reasoning=capability=None
skills=planner=healer=improver_v2=meta=None
rag=web_search=vision=router=benchmark=None
voice=collab=kg=conv_mgr=None
plugins=researcher=projects=prompts=None
# v7
hypothesis=uncertainty=consolidation=ctx_optimizer=intel_monitor=None


@asynccontextmanager
async def lifespan(app):
    global llm,memory,tools,orchestrator,reasoning,capability
    global skills,planner,healer,improver_v2,meta
    global rag,web_search,vision,router,benchmark
    global voice,collab,kg,conv_mgr
    global plugins,researcher,projects,prompts
    global hypothesis,uncertainty,consolidation,ctx_optimizer,intel_monitor

    log.info("🚀 Booting Synapse Local v7…")
    t0 = time.time()

    # Core systems (v1-v6)
    llm          = LLMService(Config.OLLAMA_BASE_URL, Config.GENERAL_MODEL, Config.CODER_MODEL)
    memory       = MemoryService(Config.CHROMA_PATH, Config.EMBEDDING_MODEL)
    await memory.init()
    tools        = ToolRegistry()
    orchestrator = AgentOrchestrator(llm, memory, tools)
    reasoning    = ReasoningEngine(llm)
    skills       = SkillLibrary(llm, memory)
    capability   = CapabilityEngine(llm, tools, memory)
    planner      = Planner(llm, orchestrator, tools)
    healer       = SelfHealingMonitor(llm, Config)
    improver_v2  = SelfImprovementV2(llm, tools, skills, Config.MAX_ITERATIONS)
    meta         = MetaAgent(llm, orchestrator, planner, reasoning, capability, skills, tools, memory)
    rag          = RAGEngine(llm, memory)
    web_search   = WebSearchEngine(llm)
    vision       = VisionEngine(Config.OLLAMA_BASE_URL)
    router       = ModelRouter(Config.OLLAMA_BASE_URL, llm)
    benchmark    = BenchmarkEngine(llm, tools)
    voice        = VoiceEngine()
    collab       = MultiAgentCollaboration(llm)
    kg           = KnowledgeGraph(llm)
    conv_mgr     = ConversationManager(llm)
    plugins      = PluginSystem(llm, tools, capability)
    researcher   = DeepResearcher(llm, web_search, memory)
    projects     = ProjectManager()
    prompts      = PromptLibrary(llm)

    # v7 intelligence upgrades
    hypothesis      = HypothesisEngine(llm, tools)
    uncertainty     = UncertaintyEngine(llm)
    consolidation   = MemoryConsolidation(llm, memory)
    ctx_optimizer   = ContextOptimizer(llm)
    intel_monitor   = IntelligenceMonitor(llm)

    # Health checks
    async def chk_ollama(): ok=await llm.ping(); return ok,(None if ok else "Ollama not responding")
    async def chk_memory():
        try: await memory.collection_count(); return True,None
        except Exception as e: return False,str(e)
    healer.register_check("ollama", chk_ollama)
    healer.register_check("memory", chk_memory)

    # Background tasks
    asyncio.create_task(router.discover())
    asyncio.create_task(vision.detect_vision_model())
    asyncio.create_task(voice.init())
    asyncio.create_task(healer.start(Config.HEAL_INTERVAL_SEC))
    asyncio.create_task(
        consolidation.start_background(Config.CONSOLIDATION_INTERVAL_H)
    )

    log.info(f"✅ All v7 systems online in {time.time()-t0:.1f}s")
    yield
    healer.stop()
    consolidation.stop_background()
    await web_search.close()


app = FastAPI(title="Synapse Local API", version="7.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ════════════════════════════════════════════════
# REQUEST MODELS
# ════════════════════════════════════════════════
class ChatReq(BaseModel):
    message: str; session_id: str="default"; use_agent: bool=True
    stream: bool=True; use_meta: bool=True; project_id: str=""
    use_uncertainty: bool=False
class MemSearchReq(BaseModel): query: str; n_results: int=5
class ImproveReq(BaseModel):
    code: str=""; goal: str=""; language: str="python"; mode: str="improve"; max_iterations: int=5
class PlanReq(BaseModel): goal: str; context: str=""; session_id: str="default"; stream: bool=True
class CapReq(BaseModel): user_request: str; failure_reason: str=""
class CreateToolReq(BaseModel):
    tool_name: str; tool_description: str; tool_purpose: str; example_params: dict={}; test_after_create: bool=True
class ReasonReq(BaseModel): task: str; strategy: str="auto"; context: str=""; role: str="general"
class SkillReq(BaseModel): task: str; response: str; score: float=7.0; agent_role: str="general"; session_id: str="default"
class ToolReq(BaseModel): tool: str; params: dict
class KnowledgeReq(BaseModel): topic: str; session_id: str="default"
class RAGQueryReq(BaseModel): question: str; doc_id: Optional[str]=None; n_chunks: int=6; stream: bool=False
class WebSearchReq(BaseModel): query: str; n: int=8; summarise: bool=True; stream: bool=False
class VisionReq(BaseModel): image_b64: str; task: str="describe"; question: str=""
class VisionUrlReq(BaseModel): url: str; task: str="describe"; question: str=""
class BenchReq(BaseModel): suite: str="coding"; model: str=""; stream: bool=True
class TTSReq(BaseModel): text: str; voice: str=""; speed: float=1.0
class CollabReq(BaseModel): topic: str; mode: str="council"; agents: Optional[List[str]]=None; rounds: int=2; stream: bool=True
class KGExtractReq(BaseModel): text: str; source: str=""
class KGQueryReq(BaseModel): question: str; depth: int=2
class KGRelationReq(BaseModel): from_id: str; relation: str; to_id: str; weight: float=1.0; source: str=""
class ConvExportReq(BaseModel): session_id: str; format: str="markdown"
class ConvSearchReq(BaseModel): query: str; limit: int=20
class PluginInstallReq(BaseModel): package: str; description: str=""; auto_generate_tools: bool=True
class ResearchReq(BaseModel): topic: str; depth: str="standard"; stream: bool=True; use_memory: bool=True
class ProjectCreateReq(BaseModel): name: str; description: str=""; tech_stack: List[str]=[]; goals: List[str]=[]; ai_context: str=""
class ProjectUpdateReq(BaseModel): name: Optional[str]=None; description: Optional[str]=None; status: Optional[str]=None; ai_context: Optional[str]=None
class TaskCreateReq(BaseModel): title: str; description: str=""; priority: int=3; agent_role: str=""
class TaskUpdateReq(BaseModel): status: Optional[str]=None; title: Optional[str]=None; priority: Optional[int]=None
class NoteCreateReq(BaseModel): title: str; content: str
class PromptCreateReq(BaseModel): name: str; template: str; category: str="general"; tags: List[str]=[]; description: str=""
class PromptGenerateReq(BaseModel): use_case: str; category: str="general"; example: str=""
class PromptApplyReq(BaseModel): template_id: str; variables: Dict[str,str]={}
# v7 new models
class HypothesisReq(BaseModel):
    observation: str; n: int=3; max_iterations: int=3; stream: bool=True
class HypothesisTestReq(BaseModel): observation: str; hypothesis_id: str; evidence: str
class CausalReq(BaseModel): situation: str
class AbductiveReq(BaseModel): observations: List[str]
class ArgumentReq(BaseModel): argument: str
class ThoughtChainReq(BaseModel): question: str; context: str=""; stream: bool=True
class UncertaintyReq(BaseModel): question: str
class UncertaintyAnswerReq(BaseModel): question: str; context: str=""; stream: bool=True
class SocraticReq(BaseModel): request: str
class SelfDoubtReq(BaseModel): question: str; answer: str
class ConsolidationReq(BaseModel): session_id: str="default"; aggressive: bool=False
class ContextBuildReq(BaseModel):
    query: str; sources: Dict[str,List[str]]={};max_tokens: int=6000; structure: bool=True
class IntelEvalReq(BaseModel): task: str; response: str; agent_role: str="general"; session_id: str="default"


# ════════════════════════════════════════════════
# HEALTH
# ════════════════════════════════════════════════
@app.get("/health")
async def health():
    ok = await llm.ping()
    return {
        "status":  "ok" if ok else "degraded", "version":"7.0.0","ollama":ok,
        "models":  await llm.list_models(), "memory":await memory.collection_count(),
        "skills":  skills.stats(), "capabilities":capability.stats(),
        "rag":     rag.stats(), "router":router.stats(),
        "voice":   voice.status(), "vision":vision.is_available(),
        "kg":      kg.stats(), "conversations":conv_mgr.analytics(),
        "plugins": plugins.stats(), "projects":projects.stats(), "prompts":prompts.stats(),
        "meta":    meta.stats(), "healing":healer.get_status(),
        # v7
        "uncertainty":   uncertainty.stats(),
        "consolidation": consolidation.stats(),
        "intelligence":  intel_monitor.stats(),
        "ctx_optimizer": ctx_optimizer.stats(),
    }

@app.get("/system/status")
async def sys_status():
    return {
        "health":        healer.get_status(),
        "skills":        skills.stats(), "capabilities":capability.stats(),
        "rag":           rag.stats(), "kg":kg.stats(),
        "plugins":       plugins.stats(), "projects":projects.stats(), "prompts":prompts.stats(),
        "router":        router.stats(), "voice":voice.status(),
        "conversations": conv_mgr.analytics(), "meta":meta.stats(),
        "intelligence":  intel_monitor.stats(),
        "consolidation": consolidation.stats(),
        "uncertainty":   uncertainty.stats(),
        "tools":         [t["name"] for t in tools.list_tools()],
        "memory":        await memory.collection_count(),
    }

@app.get("/evolution")
async def evolution(limit: int=50):
    return {"log":meta.evolution_log(limit),"stats":meta.stats()}


# ════════════════════════════════════════════════
# CHAT — intelligence-upgraded
# ════════════════════════════════════════════════
@app.post("/chat")
async def chat(req: ChatReq, bg: BackgroundTasks):
    # Build optimized context using ContextOptimizer
    mem_ctx = await memory.search(req.message, n=Config.MAX_MEMORY_RESULTS)
    rel_skills = await skills.get_relevant_skills(req.message, n=2)
    sources = {
        "memory": [m["text"] for m in mem_ctx],
        "skill":  [f"{s.name}: {s.reusable_pattern}" for s in rel_skills],
    }
    if req.project_id:
        proj_ctx = projects.get_ai_context(req.project_id)
        if proj_ctx: sources["project"] = [proj_ctx]

    ctx_block = await ctx_optimizer.build(
        req.message, sources,
        max_tokens=Config.CONTEXT_MAX_TOKENS,
        structure=Config.CONTEXT_STRUCTURE,
    )

    if req.stream:
        async def sse():
            full=""; agent_role=""; strategy=""
            if req.use_uncertainty:
                # Uncertainty-aware answering
                async for chunk in uncertainty.answer_with_uncertainty(req.message, ctx_block):
                    full += chunk; yield f"data: {json.dumps({'chunk':chunk,'type':'token'})}\n\n"
            elif req.use_meta:
                async for chunk in meta.run_stream(req.message, req.session_id):
                    if chunk.startswith("[META:"):
                        parts = chunk[6:chunk.index("]")].split(":")
                        strategy = parts[0].lower()
                        yield f"data: {json.dumps({'type':'meta_route','strategy':strategy})}\n\n"
                    elif chunk.startswith("[AGENT:"):
                        agent_role = chunk[7:chunk.index("]")]
                        yield f"data: {json.dumps({'type':'agent_role','role':agent_role})}\n\n"
                    else:
                        full += chunk; yield f"data: {json.dumps({'chunk':chunk,'type':'token'})}\n\n"
            else:
                async for chunk in orchestrator.run_stream(req.message, req.session_id, ctx_block):
                    if not chunk.startswith("[AGENT:"): full+=chunk; yield f"data: {json.dumps({'chunk':chunk,'type':'token'})}\n\n"

            conv_mgr.save_message(req.session_id,"user",req.message)
            conv_mgr.save_message(req.session_id,"assistant",full,agent_role,strategy)
            bg.add_task(skills.learn_from_interaction,req.message,full,agent_role,7.0,req.session_id)

            # Background intelligence evaluation (sampled)
            if Config.INTEL_MONITOR_ENABLED and random.random() < Config.INTEL_EVAL_RATE:
                bg.add_task(intel_monitor.evaluate,req.message,full,agent_role,req.session_id)

            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(sse(), media_type="text/event-stream")
    else:
        result = await meta.run(req.message, req.session_id)
        resp = result["response"]
        conv_mgr.save_message(req.session_id,"user",req.message)
        conv_mgr.save_message(req.session_id,"assistant",resp)
        if Config.INTEL_MONITOR_ENABLED and random.random() < Config.INTEL_EVAL_RATE:
            bg.add_task(intel_monitor.evaluate,req.message,resp)
        return {"response":resp,"strategy":result["strategy"]}


# ════════════════════════════════════════════════
# HYPOTHESIS ENGINE (v7)
# ════════════════════════════════════════════════
@app.post("/hypothesis/generate")
async def hyp_generate(req: HypothesisReq):
    if req.stream:
        async def gen():
            async for c in hypothesis.iterate_stream(req.observation, req.max_iterations):
                yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    hyp_set = await hypothesis.generate(req.observation, req.n)
    return {"observation":hyp_set.observation,
            "hypotheses":[asdict(h) for h in hyp_set.hypotheses]}

@app.post("/hypothesis/auto-test")
async def hyp_auto_test(req: HypothesisReq):
    result = await hypothesis.auto_test(req.observation)
    return result

@app.post("/hypothesis/causal")
async def hyp_causal(req: CausalReq):
    return await hypothesis.causal_analysis(req.situation)

@app.post("/hypothesis/abductive")
async def hyp_abductive(req: AbductiveReq):
    return await hypothesis.abductive(req.observations)

@app.post("/hypothesis/argument")
async def hyp_argument(req: ArgumentReq):
    return await hypothesis.analyze_argument(req.argument)

@app.post("/hypothesis/think-explicitly")
async def hyp_think(req: ThoughtChainReq):
    if req.stream:
        async def gen():
            async for c in hypothesis.think_explicitly(req.question, req.context):
                yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    full = ""
    async for c in hypothesis.think_explicitly(req.question, req.context): full += c
    return {"thought_chain": full}


# ════════════════════════════════════════════════
# UNCERTAINTY ENGINE (v7)
# ════════════════════════════════════════════════
@app.post("/uncertainty/assess")
async def unc_assess(req: UncertaintyReq):
    report = await uncertainty.assess(req.question)
    return asdict_report(report)

@app.post("/uncertainty/answer")
async def unc_answer(req: UncertaintyAnswerReq):
    if req.stream:
        async def gen():
            async for c in uncertainty.answer_with_uncertainty(req.question, req.context):
                yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    full=""
    async for c in uncertainty.answer_with_uncertainty(req.question,req.context): full+=c
    return {"answer":full}

@app.post("/uncertainty/socratic")
async def unc_socratic(req: SocraticReq):
    return await uncertainty.socratic_check(req.request)

@app.post("/uncertainty/self-doubt")
async def unc_doubt(req: SelfDoubtReq):
    return await uncertainty.self_doubt(req.question, req.answer)

@app.get("/uncertainty/stats")
async def unc_stats(): return uncertainty.stats()


# ════════════════════════════════════════════════
# MEMORY CONSOLIDATION (v7)
# ════════════════════════════════════════════════
@app.post("/consolidation/run")
async def run_consolidation(req: ConsolidationReq):
    stats = await consolidation.consolidate(req.session_id, req.aggressive)
    return asdict(stats)

@app.post("/consolidation/run-all")
async def consolidate_all():
    return await consolidation.force_consolidate_all()

@app.get("/consolidation/history")
async def consolidation_history(limit: int=10):
    return {"history":consolidation.consolidation_history(limit),"stats":consolidation.stats()}


# ════════════════════════════════════════════════
# CONTEXT OPTIMIZER (v7)
# ════════════════════════════════════════════════
@app.post("/context/build")
async def build_context(req: ContextBuildReq):
    ctx = await ctx_optimizer.build(req.query,req.sources,req.max_tokens,req.structure)
    analysis = ctx_optimizer.analyse(ctx, req.query)
    return {"context":ctx,"analysis":analysis}

@app.post("/context/analyse")
async def analyse_context(req: ContextBuildReq):
    ctx = req.sources.get("text", [""])[0] if req.sources else ""
    return ctx_optimizer.analyse(ctx, req.query)


# ════════════════════════════════════════════════
# INTELLIGENCE MONITOR (v7)
# ════════════════════════════════════════════════
@app.post("/intelligence/evaluate")
async def intel_eval(req: IntelEvalReq):
    score = await intel_monitor.evaluate(req.task,req.response,req.agent_role,req.session_id)
    return asdict(score)

@app.get("/intelligence/profile")
async def intel_profile(days: int=7):
    p = intel_monitor.get_profile(days)
    return asdict(p)

@app.get("/intelligence/growth")
async def intel_growth(days: int=30, bucket_hours: int=24):
    return {"chart": intel_monitor.growth_chart(days, bucket_hours)}

@app.get("/intelligence/dimensions")
async def intel_dimensions():
    return {"dimensions": intel_monitor.dimension_breakdown()}

@app.get("/intelligence/milestones")
async def intel_milestones():
    return {"milestones":intel_monitor.list_milestones(),"stats":intel_monitor.stats()}

@app.get("/intelligence/stats")
async def intel_stats(): return intel_monitor.stats()


# ════════════════════════════════════════════════
# ALL V1-V6 ENDPOINTS (preserved)
# ════════════════════════════════════════════════
# RAG
@app.post("/rag/upload")
async def rag_upload(file: UploadFile=File(...)): d=await file.read(); return await rag.ingest(d,file.filename)
@app.post("/rag/query")
async def rag_query(req: RAGQueryReq):
    if req.stream:
        async def g():
            async for c in rag.query_stream(req.question,req.doc_id,req.n_chunks): yield f"data: {json.dumps({'chunk':c})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    return await rag.query(req.question,req.doc_id,req.n_chunks)
@app.get("/rag/docs")
async def rag_list(): return {"documents":rag.list_docs(),"stats":rag.stats()}
@app.post("/rag/summarise/{doc_id}")
async def rag_sum(doc_id: str): return await rag.summarise(doc_id)
@app.delete("/rag/docs/{doc_id}")
async def rag_del(doc_id: str): return {"deleted":await rag.delete_doc(doc_id)}

# Search / Vision
@app.post("/search")
async def search(req: WebSearchReq):
    if req.stream:
        async def g():
            async for c in web_search.search_stream(req.query,req.n):
                if c.startswith("[SEARCH_RESULTS]"): yield f"data: {json.dumps({'type':'search_results','results':json.loads(c[len('[SEARCH_RESULTS]'):])})}\n\n"
                else: yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    return await web_search.search(req.query,req.n,req.summarise)
@app.post("/vision/analyse")
async def vis_an(req: VisionReq):
    try: img=base64.b64decode(req.image_b64)
    except: return {"success":False,"error":"Invalid base64"}
    return await vision.analyse(img,req.task,req.question)
@app.post("/vision/analyse/stream")
async def vis_str(req: VisionReq):
    try: img=base64.b64decode(req.image_b64)
    except: return {"success":False,"error":"Invalid base64"}
    async def g():
        async for c in vision.analyse_stream(img,req.task,req.question): yield f"data: {json.dumps({'chunk':c})}\n\n"
    return StreamingResponse(g(),media_type="text/event-stream")
@app.post("/vision/upload")
async def vis_up(file: UploadFile=File(...),task: str=Form("describe"),question: str=Form("")):
    d=await file.read(); return await vision.analyse(d,task,question)
@app.post("/vision/url")
async def vis_url(req: VisionUrlReq): return await vision.analyse_url(req.url,req.task,req.question)
@app.get("/vision/tasks")
async def vis_tasks(): return {"tasks":vision.available_tasks(),"model":vision._model,"available":vision.is_available()}

# Voice
@app.post("/voice/transcribe")
async def transcribe(file: UploadFile=File(...),language: str=Form("auto")):
    d=await file.read(); fmt=file.filename.split(".")[-1] if file.filename else "webm"; return await voice.transcribe(d,language,fmt)
@app.post("/voice/tts")
async def tts(req: TTSReq):
    r=await voice.synthesise(req.text,req.voice,req.speed)
    if not r.get("success"): raise HTTPException(400,r.get("error","TTS failed"))
    ab=base64.b64decode(r["audio_b64"]); fmt=r.get("format","mp3")
    return Response(content=ab,media_type="audio/mpeg" if fmt=="mp3" else "audio/wav")
@app.post("/voice/tts/b64")
async def tts_b64(req: TTSReq): return await voice.synthesise(req.text,req.voice,req.speed)
@app.get("/voice/voices")
async def voices(): return await voice.list_voices()
@app.get("/voice/status")
async def voice_status(): return voice.status()

# Collab / KG / Conversations
@app.post("/collab/run")
async def collab_run(req: CollabReq):
    if req.stream:
        async def g():
            async for c in collab.run_stream(req.topic,req.mode,req.agents,req.rounds):
                if c.startswith("[COLLAB_START]"): yield f"data: {json.dumps({'type':'collab_start'})}\n\n"
                else: yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    return asdict(await collab.run(req.topic,req.mode,req.agents,req.rounds))
@app.get("/collab/roles")
async def collab_roles(): return {"roles":collab.list_roles()}
@app.get("/collab/modes")
async def collab_modes(): return {"modes":collab.list_modes()}
@app.post("/kg/extract")
async def kg_ex(req: KGExtractReq): return await kg.extract_and_add(req.text,req.source)
@app.post("/kg/query")
async def kg_q(req: KGQueryReq): return await kg.query(req.question,req.depth)
@app.get("/kg/search")
async def kg_s(q: str="",entity_type: str="",limit: int=20): return {"entities":kg.search_entities(q,entity_type,limit)}
@app.get("/kg/viz")
async def kg_v(limit: int=100): return kg.get_viz_data(limit)
@app.get("/kg/stats")
async def kg_st(): return kg.stats()
@app.post("/kg/relation")
async def kg_r(req: KGRelationReq): return {"added":kg.add_relation(req.from_id,req.relation,req.to_id,req.weight,req.source)}
@app.delete("/kg/entity/{eid}")
async def kg_d(eid: str): return {"deleted":kg.delete_entity(eid)}
@app.get("/conversations")
async def list_c(limit: int=50,offset: int=0,search: str=""): return {"sessions":conv_mgr.list_sessions(limit,offset,search)}
@app.get("/conversations/{sid}")
async def get_c(sid: str): s=conv_mgr.get_session(sid); return s or HTTPException(404,"Not found")
@app.get("/conversations/{sid}/messages")
async def get_m(sid: str,limit: int=100): return {"messages":conv_mgr.get_messages(sid,limit)}
@app.post("/conversations/{sid}/summarise")
async def sum_c(sid: str): return await conv_mgr.summarise_session(sid)
@app.post("/conversations/export")
async def exp_c(req: ConvExportReq):
    c=conv_mgr.export_session(req.session_id,req.format)
    if not c: raise HTTPException(404,"Not found")
    m={"markdown":"text/markdown","json":"application/json","text":"text/plain"}.get(req.format,"text/plain")
    return Response(content=c,media_type=m,headers={"Content-Disposition":f"attachment; filename=sess.{req.format}"})
@app.post("/conversations/search")
async def srch_c(req: ConvSearchReq): return {"messages":conv_mgr.search_messages(req.query,req.limit)}
@app.get("/conversations/analytics/summary")
async def ca(): return conv_mgr.analytics()
@app.delete("/conversations/{sid}")
async def del_c(sid: str): return {"deleted":conv_mgr.delete_session(sid)}

# Plugins / Research / Projects / Prompts
@app.post("/plugins/install")
async def plug_in(req: PluginInstallReq): return await plugins.add_plugin(req.package,req.description,req.auto_generate_tools)
@app.delete("/plugins/{pkg}")
async def plug_rm(pkg: str): return await plugins.remove_plugin(pkg)
@app.get("/plugins/list")
async def plug_ls(): return {"plugins":plugins.list_plugins(),"stats":plugins.stats()}
@app.get("/plugins/allowed")
async def plug_al(): return {"packages":plugins.list_allowed()}
@app.post("/research")
async def rsrch(req: ResearchReq):
    if req.stream:
        async def g():
            async for c in researcher.research_stream(req.topic,req.depth): yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    rpt=await researcher.research(req.topic,req.depth,req.use_memory)
    return {"title":rpt.title,"sections":rpt.sections,"citations":rpt.citations,"confidence":rpt.confidence,"markdown":researcher.format_report(rpt)}

@app.post("/projects")
async def c_proj(req: ProjectCreateReq): return asdict(projects.create_project(req.name,req.description,req.tech_stack,req.goals,req.ai_context))
@app.get("/projects")
async def l_proj(status: str=""): return {"projects":projects.list_projects(status),"stats":projects.stats()}
@app.get("/projects/{pid}")
async def g_proj(pid: str): p=projects.get_project(pid); return asdict(p) if p else HTTPException(404,"Not found")
@app.patch("/projects/{pid}")
async def u_proj(pid: str,req: ProjectUpdateReq): return {"updated":projects.update_project(pid,**{k:v for k,v in req.model_dump().items() if v is not None})}
@app.delete("/projects/{pid}")
async def d_proj(pid: str): return {"deleted":projects.delete_project(pid)}
@app.post("/projects/{pid}/tasks")
async def c_task(pid: str,req: TaskCreateReq): return asdict(projects.add_task(pid,req.title,req.description,req.priority,req.agent_role))
@app.get("/projects/{pid}/tasks")
async def l_task(pid: str,status: str=""): return {"tasks":projects.list_tasks(pid,status)}
@app.patch("/projects/{pid}/tasks/{tid}")
async def u_task(pid: str,tid: str,req: TaskUpdateReq): return {"updated":projects.update_task(tid,**{k:v for k,v in req.model_dump().items() if v is not None})}
@app.delete("/projects/{pid}/tasks/{tid}")
async def d_task(pid: str,tid: str): return {"deleted":projects.delete_task(tid)}
@app.post("/projects/{pid}/notes")
async def c_note(pid: str,req: NoteCreateReq): return projects.add_note(pid,req.title,req.content)
@app.get("/projects/{pid}/notes")
async def l_note(pid: str): return {"notes":projects.list_notes(pid)}
@app.post("/projects/{pid}/files")
async def up_file(pid: str,file: UploadFile=File(...)): d=await file.read(); return projects.save_file(pid,file.filename,d)
@app.get("/projects/{pid}/files")
async def l_file(pid: str): return {"files":projects.list_files(pid)}
@app.get("/projects/{pid}/context")
async def p_ctx(pid: str): return {"context":projects.get_ai_context(pid)}

@app.post("/prompts")
async def c_prom(req: PromptCreateReq): return asdict(prompts.create(req.name,req.template,req.category,req.tags,req.description))
@app.get("/prompts")
async def l_prom(category: str="",search: str="",limit: int=50): return {"templates":prompts.list(category,search,limit),"stats":prompts.stats()}
@app.get("/prompts/categories")
async def p_cats(): return {"categories":prompts.categories(),"stats":prompts.stats()}
@app.post("/prompts/generate")
async def g_prom(req: PromptGenerateReq): return asdict(await prompts.generate(req.use_case,req.category,req.example))
@app.post("/prompts/{tid}/improve")
async def i_prom(tid: str): r=await prompts.improve(tid); return {"improved":bool(r),"template":r}
@app.post("/prompts/apply")
async def a_prom(req: PromptApplyReq): r=prompts.apply(req.template_id,req.variables); return {"prompt":r} if r else HTTPException(404,"Not found")
@app.delete("/prompts/{tid}")
async def d_prom(tid: str): return {"deleted":prompts.delete(tid)}

# Router / Benchmark / Reasoning / Plan / Improve / Capability / Skills / Healing / Memory / Tools / Agents
@app.get("/router/models")
async def r_models(): return {"models":router.list_models(),"stats":router.stats()}
@app.post("/router/discover")
async def r_disc(): p=await router.discover(); return {"discovered":len(p),"stats":router.stats()}
@app.post("/router/benchmark/{m}")
async def r_bench(m: str): return await router.benchmark(m)
@app.get("/router/route/{task}")
async def r_route(task: str): return {"task":task,"model":router.route(task)}
@app.post("/benchmark/run")
async def b_run(req: BenchReq):
    model=req.model or Config.GENERAL_MODEL
    if req.stream:
        async def g():
            async for c in benchmark.run_stream(req.suite,model): yield f"data: {json.dumps({'chunk':c,'type':'token'})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    return asdict(await benchmark.run_suite(req.suite,model))
@app.get("/benchmark/runs")
async def b_runs(limit: int=10): return {"runs":benchmark.list_runs(limit)}
@app.get("/benchmark/suites")
async def b_suites(): return {"suites":benchmark.available_suites()}
@app.post("/reasoning/think")
async def reas(req: ReasonReq): r=await reasoning.think(req.task,req.strategy,req.context,req.role); return {"strategy":r.strategy,"thinking":r.thinking,"answer":r.answer,"score":r.score}
@app.post("/reasoning/critique")
async def crit(req: ReasonReq): return await reasoning.critique(req.task,req.context)
@app.post("/reasoning/decompose")
async def decomp(req: ReasonReq): return await reasoning.decompose(req.task)
@app.post("/reasoning/think/stream")
async def reas_s(req: ReasonReq):
    async def g():
        async for c in reasoning.think_stream(req.task,req.strategy,req.context,req.role): yield f"data: {json.dumps({'chunk':c})}\n\n"
    return StreamingResponse(g(),media_type="text/event-stream")
@app.post("/plan")
async def plan(req: PlanReq):
    if req.stream:
        async def g():
            async for c in planner.execute_stream(req.goal,req.context,req.session_id): yield f"data: {json.dumps({'chunk':c})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        return StreamingResponse(g(),media_type="text/event-stream")
    r=await planner.execute(req.goal,req.context,req.session_id)
    return {"goal":r.goal,"success":r.success,"final_answer":r.final_answer,"duration_s":round(r.total_duration,2)}
@app.post("/improve")
async def improve(req: ImproveReq):
    imp=SelfImprovementV2(llm,tools,skills,max_iterations=min(req.max_iterations,8))
    return await imp.run(req.code or req.goal,req.language,req.goal,is_goal_only=(req.mode=="generate"))
@app.post("/capability/detect")
async def cap_d(req: CapReq): g=await capability.detect_capability_gap(req.user_request,req.failure_reason); return {"gap_detected":g is not None,"analysis":g}
@app.post("/capability/expand")
async def cap_e(req: CapReq): r=await capability.auto_expand(req.user_request,req.failure_reason); return r or {"success":False}
@app.post("/capability/create")
async def cap_c(req: CreateToolReq):
    r=await capability.create_tool(req.tool_name,req.tool_description,req.tool_purpose,req.example_params)
    if r["success"] and req.test_after_create and req.example_params: r["test"]=await capability.test_tool(req.tool_name,req.example_params)
    return r
@app.get("/capability/list")
async def cap_l(): return {"created_tools":capability.list_created(),"all_tools":tools.list_tools(),"stats":capability.stats()}
@app.delete("/capability/{n}")
async def cap_rm(n: str): return {"removed":capability.delete_tool(n)}
@app.post("/skills/learn")
async def sk_l(req: SkillReq):
    s=await skills.learn_from_interaction(req.task,req.response,req.agent_role,req.score,req.session_id)
    if s: return {"learned":True,"skill":asdict(s)}
    return {"learned":False}
@app.get("/skills/list")
async def sk_ls(skill_type: Optional[str]=None,limit: int=50): return {"skills":skills.list_skills(skill_type,limit),"stats":skills.stats()}
@app.post("/skills/search")
async def sk_s(req: MemSearchReq): found=await skills.get_relevant_skills(req.query,n=req.n_results); return {"skills":[asdict(s) for s in found]}
@app.post("/skills/distill")
async def sk_d(req: KnowledgeReq): k=await skills.distill_knowledge(req.topic,req.session_id); return {"success":k is not None,"knowledge":k}
@app.get("/skills/knowledge")
async def sk_k(topic: Optional[str]=None): return {"knowledge":skills.get_knowledge(topic)}
@app.delete("/skills/{sid}")
async def sk_rm(sid: str): return {"removed":skills.delete_skill(sid)}
@app.get("/healing/status")
async def h_st(): return healer.get_status()
@app.get("/healing/log")
async def h_lg(limit: int=20): return {"repairs":healer.get_repair_log(limit)}
@app.post("/healing/repair/{c}")
async def h_rp(c: str): return await healer.force_repair(c)
@app.post("/memory/search")
async def m_s(req: MemSearchReq): return {"results":await memory.search(req.query,n=req.n_results)}
@app.get("/memory/list")
async def m_l(session_id: str="default",limit: int=20): return {"memories":await memory.list_session(session_id,limit)}
@app.delete("/memory/clear")
async def m_c(session_id: Optional[str]=None): await memory.clear(session_id); return {"status":"cleared"}
@app.post("/agent/run")
async def ag_r(req: ChatReq): return await orchestrator.run(req.message,req.session_id)
@app.get("/agent/roles")
async def ag_rl(): return {"roles":list(orchestrator.agents.keys())}
@app.post("/tools/run")
async def tl_r(req: ToolReq): return {"tool":req.tool,"result":await tools.execute(req.tool,req.params)}
@app.get("/tools/list")
async def tl_l(): return {"tools":tools.list_tools()}
