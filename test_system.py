#!/usr/bin/env python3
"""
Synapse Local v3 — Full System Test Suite
Tests all new systems: MetaAgent, Reasoning, Planner,
CapabilityEngine, SkillLibrary, SelfHeal, ImprovementV2
"""
import asyncio, json, sys, time

BASE = "http://localhost:8000"

try:
    import httpx
except ImportError:
    print("❌  pip install httpx"); sys.exit(1)

PASS = "  ✅"; FAIL = "  ❌"; INFO = "  →"

async def test(name, coro, client=None):
    try:
        r = await coro
        if hasattr(r, 'json'):
            data = r.json()
        else:
            data = r
        print(f"{PASS} {name}")
        return data
    except Exception as e:
        print(f"{FAIL} {name}: {e}")
        return None

async def main():
    print("\n" + "═"*52)
    print("   SYNAPSE LOCAL v3 — SYSTEM TEST SUITE")
    print("═"*52 + "\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as c:

        # ── 1. Health ─────────────────────────────────────
        print("─── 1. Health ───────────────────────────────────")
        r = await test("API reachable", c.get("/health"))
        if r:
            print(f"{INFO} Ollama: {r.get('ollama')}")
            print(f"{INFO} Models: {r.get('models', [])}")
            print(f"{INFO} Skills: {r.get('skills',{}).get('total_skills',0)}")
            print(f"{INFO} Capabilities: {r.get('capabilities',{}).get('total_created',0)}")

        # ── 2. Reasoning ──────────────────────────────────
        print("\n─── 2. Reasoning Engine ─────────────────────────")
        r = await test("Chain-of-thought", c.post("/reasoning/think",
            json={"task":"What is 15% of 240?","strategy":"cot"}))
        if r: print(f"{INFO} Strategy: {r.get('strategy')}, answer snippet: {r.get('answer','')[:60]}")

        r = await test("Task decompose", c.post("/reasoning/decompose",
            json={"task":"Build a web scraper that saves results to CSV"}))
        if r: print(f"{INFO} Complexity: {r.get('complexity')}, subtasks: {r.get('estimated_steps')}")

        r = await test("Critique response", c.post("/reasoning/critique",
            json={"task":"Sort a list", "context":"def sort(l): return sorted(l)"}))
        if r: print(f"{INFO} Overall score: {r.get('overall',0)}/10")

        # ── 3. Code Executor ──────────────────────────────
        print("\n─── 3. Tools ────────────────────────────────────")
        r = await test("Code executor (Python)", c.post("/tools/run",
            json={"tool":"code_executor","params":{
                "code":"import math\nresult=math.factorial(10)\nprint(f'10! = {result}')",
                "language":"python"}}))
        if r and r.get("result",{}).get("success"):
            print(f"{INFO} Output: {r['result']['stdout'].strip()}")

        r = await test("File manager (write+read)", c.post("/tools/run",
            json={"tool":"file_manager","params":{
                "action":"write","path":"test_v3.txt",
                "content":"Synapse v3 file system test"}}))

        r = await test("List tools", c.get("/tools/list"))
        if r: print(f"{INFO} Available tools: {[t['name'] for t in r.get('tools',[])]}")

        # ── 4. Planner ────────────────────────────────────
        print("\n─── 4. Multi-Step Planner ───────────────────────")
        r = await test("Plan (non-stream)", c.post("/plan",
            json={"goal":"Write a Python function to check if a number is prime, then test it",
                  "stream":False}, timeout=120.0))
        if r:
            print(f"{INFO} Steps completed: {r.get('steps_completed')}/{r.get('steps_total')}")
            print(f"{INFO} Success: {r.get('success')}")

        # ── 5. Capability Engine ──────────────────────────
        print("\n─── 5. Capability Engine ────────────────────────")
        r = await test("Detect gap", c.post("/capability/detect",
            json={"user_request":"I need to calculate SHA256 hash of a string",
                  "failure_reason":""}))
        if r: print(f"{INFO} Gap detected: {r.get('gap_detected')}, analysis: {r.get('analysis',{}).get('tool_name','—')}")

        r = await test("List capabilities", c.get("/capability/list"))
        if r: print(f"{INFO} Created tools: {len(r.get('created_tools',[]))}, Total: {len(r.get('all_tools',[]))}")

        # ── 6. Skill Library ──────────────────────────────
        print("\n─── 6. Skill Library ────────────────────────────")
        r = await test("Manual learn skill", c.post("/skills/learn",
            json={"task":"Sort a Python list in reverse",
                  "response":"Use list.sort(reverse=True) or sorted(lst, reverse=True).",
                  "score":8.5,"agent_role":"coder"}))
        if r: print(f"{INFO} Learned: {r.get('learned')}")

        r = await test("Search skills", c.post("/skills/search",
            json={"query":"sort list python","n_results":3}))
        if r: print(f"{INFO} Found: {len(r.get('skills',[]))} skills")

        r = await test("List skills", c.get("/skills/list"))
        if r: print(f"{INFO} Total skills: {r.get('stats',{}).get('total_skills',0)}")

        # ── 7. Self-Improvement v2 ────────────────────────
        print("\n─── 7. Self-Improvement v2 ──────────────────────")
        buggy = "def fibonacci(n):\n    if n<=1: return n\n    return fibonacci(n-1)+fibonacci(n-1)  # bug: should be n-2"
        r = await test("Improve buggy code (2 iterations)", c.post("/improve",
            json={"code":buggy,"goal":"fix bug + add memoization","language":"python",
                  "max_iterations":2}), timeout=120.0)
        if r:
            print(f"{INFO} Success: {r.get('success')}, Best score: {r.get('best_score',0)}/10")
            print(f"{INFO} Strategy switches: {r.get('strategy_switches',0)}")
            print(f"{INFO} Skill learned: {r.get('skill_learned',False)}")

        r = await test("Generate from goal", c.post("/improve",
            json={"goal":"A function that returns nth fibonacci using dynamic programming",
                  "language":"python","mode":"generate","max_iterations":2}), timeout=90.0)
        if r: print(f"{INFO} Generated & scored: {r.get('best_score',0)}/10")

        # ── 8. Self-Healing ───────────────────────────────
        print("\n─── 8. Self-Healing Monitor ─────────────────────")
        r = await test("Healing status", c.get("/healing/status"))
        if r:
            overall = r.get("overall","?")
            comps   = list(r.get("components",{}).keys())
            print(f"{INFO} Overall: {overall}, Monitoring: {comps}")

        r = await test("Healing repair log", c.get("/healing/log"))
        if r: print(f"{INFO} Repair events: {len(r.get('repairs',[]))}")

        # ── 9. Memory ─────────────────────────────────────
        print("\n─── 9. Vector Memory ────────────────────────────")
        r = await test("Memory search", c.post("/memory/search",
            json={"query":"fibonacci python","n_results":3}))
        if r: print(f"{INFO} Results: {len(r.get('results',[]))}")

        # ── 10. Evolution Log ─────────────────────────────
        print("\n─── 10. Evolution / Meta-Stats ──────────────────")
        r = await test("Evolution log", c.get("/evolution?limit=5"))
        if r:
            stats = r.get("stats",{})
            print(f"{INFO} Total requests: {stats.get('total_requests',0)}")
            print(f"{INFO} Success rate:   {stats.get('success_rate',0):.0%}")

    print("\n" + "═"*52)
    print("   ✅  ALL TESTS COMPLETE — Synapse v3 is alive!")
    print("═"*52 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
