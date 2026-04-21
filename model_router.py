"""
Model Router — Smart Model Selection
Profiles every installed Ollama model, benchmarks speed/quality,
then automatically routes each task to the best available model.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

import httpx

log = logging.getLogger("synapse.router")

PROFILES_PATH = Path("./data/model_profiles.json")
PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)

# Task categories and their ideal model characteristics
TASK_MATRIX = {
    "code":       {"prefer": ["deepseek", "coder", "codellama", "starcoder"],
                   "min_params": 7},
    "reasoning":  {"prefer": ["llama3", "mistral", "gemma", "qwen"],
                   "min_params": 7},
    "chat":       {"prefer": ["llama3", "mistral", "phi", "gemma"],
                   "min_params": 3},
    "math":       {"prefer": ["deepseek", "mathstral", "llama3"],
                   "min_params": 7},
    "vision":     {"prefer": ["llava", "bakllava", "moondream"],
                   "min_params": 7},
    "embed":      {"prefer": ["nomic", "mxbai", "all-minilm"],
                   "min_params": 0},
    "fast":       {"prefer": ["phi", "tinyllama", "gemma:2b", "llama3:8b"],
                   "min_params": 0},
    "long_ctx":   {"prefer": ["llama3", "mistral", "gemma"],
                   "min_params": 7},
}

BENCHMARK_PROMPT = "Write a Python function to compute the nth Fibonacci number efficiently."


@dataclass
class ModelProfile:
    name:        str
    size_gb:     float
    params_b:    float
    family:      str
    capabilities: List[str]   # ["chat","code","vision","embed"]
    tokens_per_sec: float
    quality_score:  float     # 0-10
    context_len:    int
    is_vision:      bool
    is_embed:       bool
    last_tested:    float


class ModelRouter:
    def __init__(self, ollama_base_url: str, llm):
        self.base_url  = ollama_base_url.rstrip("/")
        self.llm       = llm
        self._profiles: Dict[str, ModelProfile] = {}
        self._client   = httpx.AsyncClient(timeout=30.0)
        self._load_profiles()

    # ── Profile Discovery ─────────────────────────────────────────────────────
    async def discover(self) -> List[ModelProfile]:
        """Fetch all installed models and build/update profiles."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            models = resp.json().get("models", [])
        except Exception as e:
            log.error(f"Model discovery error: {e}")
            return list(self._profiles.values())

        for m in models:
            name = m.get("name", "")
            if name and name not in self._profiles:
                profile = self._build_profile(m)
                self._profiles[name] = profile

        self._save_profiles()
        log.info(f"Discovered {len(self._profiles)} model(s)")
        return list(self._profiles.values())

    def _build_profile(self, model_info: dict) -> ModelProfile:
        name    = model_info.get("name", "")
        size    = model_info.get("size", 0)
        size_gb = size / (1024 ** 3)
        details = model_info.get("details", {})

        # Estimate params from name
        params = self._estimate_params(name)

        # Detect family
        family = self._detect_family(name)

        # Capabilities
        caps = ["chat"]
        nl   = name.lower()
        if any(k in nl for k in ["coder","code","starcoder","deepseek-coder"]):
            caps.append("code")
        if any(k in nl for k in ["llava","bakllava","moondream","vision"]):
            caps.append("vision")
        if any(k in nl for k in ["nomic","embed","minilm","mxbai"]):
            caps = ["embed"]

        return ModelProfile(
            name=name, size_gb=round(size_gb, 1), params_b=params,
            family=family, capabilities=caps,
            tokens_per_sec=0.0, quality_score=5.0,
            context_len=self._estimate_ctx(name),
            is_vision="vision" in caps,
            is_embed="embed" in caps,
            last_tested=0.0,
        )

    # ── Benchmarking ──────────────────────────────────────────────────────────
    async def benchmark(self, model_name: str) -> Dict:
        """Quick benchmark: measure tokens/sec and rough quality."""
        log.info(f"Benchmarking {model_name}…")
        start = time.time()
        full  = ""
        tokens = 0
        try:
            async with self._client.stream(
                "POST", f"{self.base_url}/api/generate",
                json={"model": model_name, "prompt": BENCHMARK_PROMPT,
                      "stream": True, "options": {"num_predict": 200}},
                timeout=60.0,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        full += d.get("response", "")
                        tokens += 1
                        if d.get("done"):
                            break
                    except Exception:
                        continue

            elapsed = time.time() - start
            tps     = round(tokens / elapsed, 1) if elapsed > 0 else 0
            quality = self._heuristic_quality(full)

            if model_name in self._profiles:
                p = self._profiles[model_name]
                p.tokens_per_sec = tps
                p.quality_score  = quality
                p.last_tested    = time.time()

            self._save_profiles()
            return {"model": model_name, "tokens_per_sec": tps,
                    "quality_score": quality, "elapsed_s": round(elapsed, 1),
                    "preview": full[:200]}
        except Exception as e:
            return {"model": model_name, "error": str(e)}

    async def benchmark_all(self) -> List[Dict]:
        await self.discover()
        results = []
        for name, profile in list(self._profiles.items()):
            if not profile.is_embed and not profile.is_vision:
                r = await self.benchmark(name)
                results.append(r)
                await asyncio.sleep(0.5)
        return results

    # ── Route ─────────────────────────────────────────────────────────────────
    def route(self, task: str, fallback: str = "llama3") -> str:
        """Return the best model name for a given task."""
        if not self._profiles:
            return fallback

        matrix  = TASK_MATRIX.get(task, TASK_MATRIX["chat"])
        prefer  = matrix.get("prefer", [])
        min_p   = matrix.get("min_params", 0)

        candidates = [
            p for p in self._profiles.values()
            if not p.is_embed
            and p.params_b >= min_p
            and (task != "vision" or p.is_vision)
            and (task == "vision" or not p.is_embed)
        ]

        if not candidates:
            return fallback

        # Score each candidate
        def score(p: ModelProfile) -> float:
            s = p.quality_score + (p.tokens_per_sec / 20)
            nl = p.name.lower()
            for i, kw in enumerate(prefer):
                if kw.lower() in nl:
                    s += (len(prefer) - i) * 2   # prefer earlier matches more
            return s

        best = max(candidates, key=score)
        log.debug(f"Route '{task}' → {best.name}")
        return best.name

    def route_for_prompt(self, prompt: str) -> str:
        """Auto-detect task from prompt content and route."""
        p = prompt.lower()
        if any(k in p for k in ["def ","class ","function","import ","bug","error","fix"]):
            return self.route("code")
        if any(k in p for k in ["solve","calculate","prove","equation","math"]):
            return self.route("math")
        if any(k in p for k in ["why","explain","analyse","think through","reason"]):
            return self.route("reasoning")
        if any(k in p for k in ["quick","briefly","short","one word","tldr"]):
            return self.route("fast")
        return self.route("chat")

    # ── List / Stats ──────────────────────────────────────────────────────────
    def list_models(self) -> List[Dict]:
        return [asdict(p) for p in sorted(
            self._profiles.values(), key=lambda x: -x.quality_score
        )]

    def get_profile(self, name: str) -> Optional[ModelProfile]:
        return self._profiles.get(name)

    def stats(self) -> Dict:
        total = len(self._profiles)
        benchmarked = sum(1 for p in self._profiles.values() if p.last_tested > 0)
        vision  = sum(1 for p in self._profiles.values() if p.is_vision)
        embed   = sum(1 for p in self._profiles.values() if p.is_embed)
        best_code = self.route("code")
        best_chat = self.route("chat")
        return {"total": total, "benchmarked": benchmarked,
                "vision": vision, "embed": embed,
                "recommended_code": best_code,
                "recommended_chat": best_chat}

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load_profiles(self):
        if PROFILES_PATH.exists():
            try:
                data = json.loads(PROFILES_PATH.read_text())
                for d in data:
                    self._profiles[d["name"]] = ModelProfile(**d)
                log.info(f"Model Router: {len(self._profiles)} profiles loaded")
            except Exception as e:
                log.warning(f"Profile load error: {e}")

    def _save_profiles(self):
        try:
            PROFILES_PATH.write_text(
                json.dumps([asdict(p) for p in self._profiles.values()], indent=2)
            )
        except Exception as e:
            log.warning(f"Profile save error: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _estimate_params(self, name: str) -> float:
        m = re.search(r"(\d+)b", name.lower())
        if m: return float(m.group(1))
        for size, params in [("small", 3), ("medium", 7), ("large", 13),
                              ("xl", 30), ("xxl", 70)]:
            if size in name.lower(): return params
        return 7.0

    def _detect_family(self, name: str) -> str:
        nl = name.lower()
        families = ["llama", "mistral", "gemma", "phi", "qwen", "deepseek",
                    "codellama", "starcoder", "nomic", "llava", "moondream"]
        for f in families:
            if f in nl: return f
        return "unknown"

    def _estimate_ctx(self, name: str) -> int:
        nl = name.lower()
        if "32k" in nl: return 32768
        if "16k" in nl: return 16384
        if "128k" in nl: return 131072
        return 8192  # safe default

    def _heuristic_quality(self, output: str) -> float:
        """Rough quality score based on output characteristics."""
        if not output: return 0.0
        score = 5.0
        if "def " in output:         score += 1.0  # wrote actual function
        if "return " in output:      score += 0.5
        if "fibonacci" in output.lower(): score += 1.0
        if len(output) > 100:        score += 0.5
        if len(output) > 300:        score += 0.5
        if "```" in output:          score += 0.5
        return min(round(score, 1), 10.0)
