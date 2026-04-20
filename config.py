import os

class Config:
    # ── Ollama ────────────────────────────────────────────────────
    OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",   "http://localhost:11434")
    GENERAL_MODEL     = os.getenv("GENERAL_MODEL",     "llama3")
    CODER_MODEL       = os.getenv("CODER_MODEL",       "deepseek-coder")
    EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL",   "nomic-embed-text")

    # ── Memory ────────────────────────────────────────────────────
    CHROMA_PATH        = os.getenv("CHROMA_PATH",       "./data/chroma")
    MAX_MEMORY_RESULTS = int(os.getenv("MAX_MEMORY_RESULTS", "5"))

    # ── Agent / Reasoning ─────────────────────────────────────────
    MAX_ITERATIONS     = int(os.getenv("MAX_ITERATIONS",    "5"))
    TOOL_TIMEOUT       = int(os.getenv("TOOL_TIMEOUT",      "30"))
    DEFAULT_REASONING  = os.getenv("DEFAULT_REASONING",     "auto")  # cot|tot|reflect|auto

    # ── Skill Library ─────────────────────────────────────────────
    SKILL_DB_PATH      = os.getenv("SKILL_DB_PATH",    "./data/skills.db")
    MIN_SCORE_TO_LEARN = float(os.getenv("MIN_SCORE_TO_LEARN", "6.0"))

    # ── Capability Engine ─────────────────────────────────────────
    CAPABILITIES_DIR   = os.getenv("CAPABILITIES_DIR", "./data/capabilities")
    MIN_GAP_CONFIDENCE = float(os.getenv("MIN_GAP_CONFIDENCE", "0.6"))

    # ── Planner ───────────────────────────────────────────────────
    MAX_PLAN_STEPS     = int(os.getenv("MAX_PLAN_STEPS",    "6"))

    # ── Self-Healing Monitor ──────────────────────────────────────
    HEAL_INTERVAL_SEC  = int(os.getenv("HEAL_INTERVAL_SEC", "60"))

    # ── Evolution / Meta-Learning ─────────────────────────────────
    EVOLUTION_LOG_PATH = os.getenv("EVOLUTION_LOG_PATH", "./data/evolution.jsonl")
    AUTO_EXPAND_ON_FAIL= os.getenv("AUTO_EXPAND_ON_FAIL", "true").lower() == "true"

    # ── Server ────────────────────────────────────────────────────
    HOST               = os.getenv("HOST", "0.0.0.0")
    PORT               = int(os.getenv("PORT", "8000"))

    # ── Security ──────────────────────────────────────────────────
    ALLOWED_DIRS       = os.getenv("ALLOWED_DIRS",   "./workspace").split(",")
    MAX_CODE_RUNTIME   = int(os.getenv("MAX_CODE_RUNTIME", "20"))

    # ── RAG ───────────────────────────────────────────────────────────────
    DOCS_DIR         = os.getenv("DOCS_DIR",         "./data/documents")
    MAX_DOC_SIZE_MB  = int(os.getenv("MAX_DOC_SIZE_MB",  "50"))
    RAG_CHUNK_SIZE   = int(os.getenv("RAG_CHUNK_SIZE",   "800"))
    RAG_CHUNKS_CTX   = int(os.getenv("RAG_CHUNKS_CTX",   "6"))

    # ── Web Search ────────────────────────────────────────────────────────
    WEB_SEARCH_N     = int(os.getenv("WEB_SEARCH_N",     "8"))
    WEB_CACHE_TTL    = int(os.getenv("WEB_CACHE_TTL",    "300"))

    # ── Vision ────────────────────────────────────────────────────────────
    VISION_MODEL     = os.getenv("VISION_MODEL",     "llava")
    MAX_IMAGE_MB     = int(os.getenv("MAX_IMAGE_MB",     "10"))

    # ── Model Router ──────────────────────────────────────────────────────
    ROUTER_ENABLED   = os.getenv("ROUTER_ENABLED",   "true").lower() == "true"
    PROFILES_PATH    = os.getenv("PROFILES_PATH",    "./data/model_profiles.json")

    # ── Benchmark ─────────────────────────────────────────────────────────
    BENCH_DIR        = os.getenv("BENCH_DIR",        "./data/benchmarks")

    # ── Voice ─────────────────────────────────────────────────────────────────
    VOICE_ENABLED    = os.getenv("VOICE_ENABLED",    "true").lower() == "true"
    WHISPER_MODEL    = os.getenv("WHISPER_MODEL",    "base")
    TTS_ENGINE       = os.getenv("TTS_ENGINE",       "auto")  # edge-tts|pyttsx3|espeak|auto
    DEFAULT_VOICE    = os.getenv("DEFAULT_VOICE",    "en-US-AriaNeural")

    # ── Collaboration ─────────────────────────────────────────────────────────
    COLLAB_MAX_ROUNDS = int(os.getenv("COLLAB_MAX_ROUNDS", "3"))

    # ── Knowledge Graph ───────────────────────────────────────────────────────
    KG_DB_PATH       = os.getenv("KG_DB_PATH",       "./data/knowledge_graph.db")
    KG_MAX_DEPTH     = int(os.getenv("KG_MAX_DEPTH", "3"))

    # ── Conversations ─────────────────────────────────────────────────────────
    CONV_DB_PATH     = os.getenv("CONV_DB_PATH",     "./data/conversations.db")
    CONV_AUTO_SUMMARISE = os.getenv("CONV_AUTO_SUMMARISE", "false").lower() == "true"

    # ── Plugin System ─────────────────────────────────────────────────────────
    PLUGINS_DIR      = os.getenv("PLUGINS_DIR",      "./data/plugins")
    AUTO_INSTALL_PKGS= os.getenv("AUTO_INSTALL_PKGS","false").lower() == "true"

    # ── Deep Researcher ───────────────────────────────────────────────────────
    RESEARCH_DEFAULT_DEPTH = os.getenv("RESEARCH_DEFAULT_DEPTH", "standard")
    RESEARCH_MAX_QUERIES   = int(os.getenv("RESEARCH_MAX_QUERIES", "6"))

    # ── Project Manager ───────────────────────────────────────────────────────
    PROJECTS_DB     = os.getenv("PROJECTS_DB",      "./data/projects.db")
    PROJECTS_DIR    = os.getenv("PROJECTS_DIR_PATH", "./data/project_files")

    # ── Prompt Library ────────────────────────────────────────────────────────
    PROMPTS_DB      = os.getenv("PROMPTS_DB",        "./data/prompt_library.db")

    # ── Intelligence Upgrades ─────────────────────────────────────────────────
    # Hypothesis Engine
    HYPOTHESIS_MAX_ITER = int(os.getenv("HYPOTHESIS_MAX_ITER", "3"))
    HYPOTHESIS_MAX_N    = int(os.getenv("HYPOTHESIS_MAX_N",    "4"))

    # Uncertainty Engine
    UNCERTAINTY_ENABLED     = os.getenv("UNCERTAINTY_ENABLED", "true").lower() == "true"
    UNCERTAINTY_DOUBT_BELOW = float(os.getenv("UNCERTAINTY_DOUBT_BELOW", "0.55"))

    # Memory Consolidation
    CONSOLIDATION_INTERVAL_H = float(os.getenv("CONSOLIDATION_INTERVAL_H", "2.0"))
    CONSOLIDATION_AGGRESSIVE = os.getenv("CONSOLIDATION_AGGRESSIVE", "false").lower() == "true"

    # Context Optimizer
    CONTEXT_MAX_TOKENS   = int(os.getenv("CONTEXT_MAX_TOKENS",   "6000"))
    CONTEXT_STRUCTURE    = os.getenv("CONTEXT_STRUCTURE",  "true").lower() == "true"

    # Intelligence Monitor
    INTEL_MONITOR_ENABLED = os.getenv("INTEL_MONITOR_ENABLED", "true").lower() == "true"
    INTEL_EVAL_RATE       = float(os.getenv("INTEL_EVAL_RATE", "0.3"))  # % of responses to evaluate
