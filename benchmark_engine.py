"""
Benchmark Engine — AI Self-Evaluation System
Runs standardised test suites against the AI, measures performance,
tracks improvement over time, and exports reports.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.benchmark")

BENCH_DIR = Path("./data/benchmarks")
BENCH_DIR.mkdir(parents=True, exist_ok=True)

# ── Built-in Test Suites ──────────────────────────────────────────────────────
SUITES = {
    "coding": [
        {"id":"c1","prompt":"Write a Python function to reverse a linked list",
         "must_contain":["def ","next","None"],"category":"code"},
        {"id":"c2","prompt":"Write a binary search function in Python with comments",
         "must_contain":["def ","mid","return"],"category":"code"},
        {"id":"c3","prompt":"Write a Python decorator that measures execution time",
         "must_contain":["def ","wrapper","time"],"category":"code"},
        {"id":"c4","prompt":"Implement quicksort in Python",
         "must_contain":["def ","pivot","return"],"category":"code"},
        {"id":"c5","prompt":"Write a Python class for a simple stack with push, pop, peek",
         "must_contain":["class ","def push","def pop"],"category":"code"},
    ],
    "reasoning": [
        {"id":"r1","prompt":"If a train travels 120km in 1.5 hours, what is its speed? Show working.",
         "must_contain":["80","km"],"category":"math"},
        {"id":"r2","prompt":"What are the pros and cons of using a linked list vs array?",
         "must_contain":["memory","access","insert"],"category":"logic"},
        {"id":"r3","prompt":"Explain why recursion can cause stack overflow and how to avoid it.",
         "must_contain":["stack","depth","tail"],"category":"reasoning"},
        {"id":"r4","prompt":"A farmer has 17 sheep, all but 9 die. How many are left? Explain.",
         "must_contain":["9"],"category":"logic"},
        {"id":"r5","prompt":"What is Big O notation? Give examples of O(1), O(n), O(n²).",
         "must_contain":["O(1)","O(n)","constant"],"category":"cs_theory"},
    ],
    "language": [
        {"id":"l1","prompt":"Summarise the concept of machine learning in 3 sentences.",
         "must_contain":["data","model","learn"],"category":"nlp"},
        {"id":"l2","prompt":"Write a haiku about artificial intelligence.",
         "must_contain":[],"min_len":50,"category":"creative"},
        {"id":"l3","prompt":"Translate 'Hello, how are you?' to French, Spanish, and German.",
         "must_contain":["Bonjour","Hola","Hallo"],"category":"translation"},
        {"id":"l4","prompt":"What is the difference between 'affect' and 'effect'? Give examples.",
         "must_contain":["verb","noun","example"],"category":"grammar"},
    ],
    "tool_use": [
        {"id":"t1","prompt":"Execute Python code: print(sum(range(1,101)))",
         "use_tool":"code_executor","params":{"code":"print(sum(range(1,101)))","language":"python"},
         "expected_output":"5050","category":"tool"},
        {"id":"t2","prompt":"Calculate: what is 17 * 23 + 42?",
         "use_tool":"code_executor","params":{"code":"print(17*23+42)","language":"python"},
         "expected_output":"433","category":"tool"},
    ],
}

JUDGE_SYSTEM = """You are a strict AI response evaluator.
Given a question and a response, rate the response on:
- Correctness (0-10): is the answer factually correct?
- Completeness (0-10): does it fully answer the question?  
- Quality (0-10): is it clear, well-structured, professional?

Return ONLY valid JSON, no markdown:
{"correctness": 8, "completeness": 7, "quality": 9, "overall": 8.0, 
 "strengths": ["..."], "weaknesses": ["..."], "verdict": "pass"}
verdict must be "pass" (overall >= 6) or "fail" (overall < 6)."""


@dataclass
class TestResult:
    test_id:      str
    category:     str
    prompt:       str
    response:     str
    scores:       Dict          # correctness, completeness, quality, overall
    passed:       bool
    duration_s:   float
    must_contain_ok: bool
    llm_judge:    bool


@dataclass
class BenchmarkRun:
    run_id:        str
    suite:         str
    model:         str
    started_at:    float
    finished_at:   float
    total_tests:   int
    passed:        int
    failed:        int
    avg_score:     float
    avg_speed:     float    # tokens/sec
    results:       List[TestResult] = field(default_factory=list)


class BenchmarkEngine:
    def __init__(self, llm, tools):
        self.llm   = llm
        self.tools = tools

    # ── Run a Suite ───────────────────────────────────────────────────────────
    async def run_suite(self, suite_name: str = "coding",
                        model: str = "llama3") -> BenchmarkRun:
        """Run a full test suite and return BenchmarkRun."""
        tests = SUITES.get(suite_name, SUITES["coding"])
        run = BenchmarkRun(
            run_id     = f"{suite_name}-{int(time.time())}",
            suite      = suite_name,
            model      = model,
            started_at = time.time(),
            finished_at=0,
            total_tests= len(tests),
            passed=0, failed=0, avg_score=0, avg_speed=0,
        )

        log.info(f"Benchmark: suite={suite_name} model={model} tests={len(tests)}")
        scores = []

        for test in tests:
            tr = await self._run_single(test, model)
            run.results.append(tr)
            scores.append(tr.scores.get("overall", 0))
            if tr.passed:
                run.passed += 1
            else:
                run.failed += 1

        run.finished_at = time.time()
        run.avg_score   = round(sum(scores) / len(scores), 2) if scores else 0

        # Save to disk
        self._save_run(run)
        log.info(f"Benchmark complete: {run.passed}/{run.total_tests} passed, avg={run.avg_score}")
        return run

    # ── Run Single Test ───────────────────────────────────────────────────────
    async def _run_single(self, test: dict, model: str) -> TestResult:
        start = time.time()
        resp  = ""

        # Tool use tests
        if "use_tool" in test:
            tool_result = await self.tools.execute(
                test["use_tool"], test.get("params", {})
            )
            resp = (tool_result.get("stdout", "") or
                    tool_result.get("result", "") or
                    json.dumps(tool_result))
            scores = self._auto_score_tool(test, resp)
        else:
            # LLM generation test
            resp = await self.llm.complete(
                test["prompt"], role="general", temperature=0.3
            )
            scores = await self._judge(test["prompt"], resp)

        duration = time.time() - start

        # Must-contain check
        mc_ok = all(k.lower() in resp.lower()
                    for k in test.get("must_contain", []))

        # Min length check
        min_len = test.get("min_len", 20)
        if len(resp) < min_len:
            mc_ok = False

        # Final pass: overall >= 6 AND must_contain satisfied
        overall = scores.get("overall", 0)
        passed  = (overall >= 6.0 or test.get("use_tool")) and mc_ok

        log.info(f"  [{test['id']}] score={overall}/10 pass={passed} ({duration:.1f}s)")

        return TestResult(
            test_id=test["id"], category=test.get("category",""),
            prompt=test["prompt"], response=resp[:500],
            scores=scores, passed=passed,
            duration_s=round(duration, 2),
            must_contain_ok=mc_ok, llm_judge="use_tool" not in test,
        )

    def _auto_score_tool(self, test: dict, output: str) -> Dict:
        expected = str(test.get("expected_output", ""))
        correct  = expected in output if expected else True
        sc       = 10.0 if correct else 2.0
        return {"correctness": sc, "completeness": sc, "quality": 8.0,
                "overall": sc, "verdict": "pass" if correct else "fail"}

    async def _judge(self, prompt: str, response: str) -> Dict:
        judge_prompt = (f"Question:\n{prompt}\n\n"
                        f"Response:\n{response[:800]}\n\nEvaluate:")
        raw = await self.llm.complete(
            judge_prompt, role="general",
            system=JUDGE_SYSTEM, temperature=0.1
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            scores = json.loads(raw)
            # Compute overall if not present
            if "overall" not in scores:
                scores["overall"] = round(
                    (scores.get("correctness",5) +
                     scores.get("completeness",5) +
                     scores.get("quality",5)) / 3, 1
                )
            return scores
        except Exception:
            return {"correctness":5,"completeness":5,"quality":5,
                    "overall":5.0,"verdict":"pass"}

    # ── Stream Progress ───────────────────────────────────────────────────────
    async def run_stream(self, suite_name: str = "coding",
                         model: str = "llama3"):
        """Yield progress lines then final JSON summary."""
        tests = SUITES.get(suite_name, SUITES["coding"])
        yield f"[BENCH_START] suite={suite_name} tests={len(tests)} model={model}\n\n"

        results, scores = [], []
        for test in tests:
            yield f"**Test {test['id']}** — {test.get('category','?')}\n"
            yield f"Prompt: _{test['prompt'][:60]}…_\n"
            tr = await self._run_single(test, model)
            results.append(tr)
            scores.append(tr.scores.get("overall",0))
            icon = "✅" if tr.passed else "❌"
            yield f"{icon} Score: **{tr.scores.get('overall',0)}/10** | {tr.duration_s}s\n\n"

        avg = round(sum(scores)/len(scores), 2) if scores else 0
        passed = sum(1 for r in results if r.passed)
        yield f"---\n**Results: {passed}/{len(tests)} passed | Avg score: {avg}/10**\n"
        yield f"[BENCH_DONE]{json.dumps({'passed':passed,'total':len(tests),'avg':avg})}\n"

    # ── List / Load ───────────────────────────────────────────────────────────
    def list_runs(self, limit: int = 10) -> List[Dict]:
        runs = []
        for f in sorted(BENCH_DIR.glob("run_*.json"), reverse=True)[:limit]:
            try:
                d = json.loads(f.read_text())
                runs.append({
                    "run_id": d["run_id"], "suite": d["suite"],
                    "model": d["model"], "passed": d["passed"],
                    "total": d["total_tests"], "avg_score": d["avg_score"],
                    "finished_at": d["finished_at"],
                })
            except Exception:
                pass
        return runs

    def get_run(self, run_id: str) -> Optional[Dict]:
        f = BENCH_DIR / f"run_{run_id}.json"
        if f.exists():
            return json.loads(f.read_text())
        return None

    def available_suites(self) -> Dict:
        return {name: len(tests) for name, tests in SUITES.items()}

    def _save_run(self, run: BenchmarkRun):
        data = asdict(run)
        path = BENCH_DIR / f"run_{run.run_id}.json"
        path.write_text(json.dumps(data, indent=2))
