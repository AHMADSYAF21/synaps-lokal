"""
Meta-Agent — Autonomous Orchestrator
The top-level AI brain that decides HOW to solve a problem:
- Route to Planner (multi-step) vs direct Agent (single-step)
- Detect capability gaps → auto-create tools
- Inject learned skills into context
- Run reasoning strategies adaptively
- Log everything to evolution ledger
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

log = logging.getLogger("synapse.meta")

# Evolution log for tracking how the AI improves over time
EVOLUTION_LOG = Path("./data/evolution.jsonl")
EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)

META_ROUTER_SYSTEM = """You are the meta-intelligence of an autonomous AI system.
Given a user request, decide the EXECUTION STRATEGY.
Return ONLY valid JSON:
{
  "strategy": "direct|plan|improve|research",
  "complexity": "simple|moderate|complex",
  "needs_tools": true/false,
  "reasoning_mode": "cot|tot|reflect|none",
  "estimated_steps": 1-10,
  "rationale": "one sentence why"
}

Strategy guide:
- direct: simple Q&A, explanations, short code snippets
- plan: multi-step tasks, build systems, complex workflows
- improve: user gives code to fix/optimize
- research: gather info, analyze, synthesize knowledge"""


class MetaAgent:
    def __init__(self, llm, orchestrator, planner, reasoning,
                 capability_engine, skill_library, tools, memory):
        self.llm = llm
        self.orchestrator = orchestrator
        self.planner = planner
        self.reasoning = reasoning
        self.capability = capability_engine
        self.skills = skill_library
        self.tools = tools
        self.memory = memory
        self._request_count = 0
        self._success_count = 0

    # ── Main Entry (Streaming) ────────────────────────────────────────────────
    async def run_stream(
        self,
        user_input: str,
        session_id: str = "default",
    ) -> AsyncGenerator[str, None]:
        """Top-level streaming handler with full meta-intelligence."""
        start = time.time()
        self._request_count += 1

        # 1. Build rich context
        context = await self._build_context(user_input, session_id)

        # 2. Route to strategy
        strategy = await self._route(user_input)
        log.info(f"Meta-route: strategy={strategy['strategy']} complexity={strategy['complexity']}")

        yield f"[META:{strategy['strategy'].upper()}:{strategy['complexity'].upper()}]"

        response_text = ""
        agent_role = "meta"

        try:
            if strategy["strategy"] == "plan":
                # Multi-step planner
                async for chunk in self.planner.execute_stream(user_input, context, session_id):
                    response_text += chunk
                    yield chunk

            elif strategy["strategy"] == "improve":
                # Code improvement mode — let agent handle it
                async for chunk in self.orchestrator.run_stream(user_input, session_id, context):
                    if chunk.startswith("[AGENT:"):
                        agent_role = chunk[7:chunk.index("]")]
                        yield chunk
                        continue
                    response_text += chunk
                    yield chunk

            elif strategy["reasoning_mode"] in ("tot", "reflect"):
                # Advanced reasoning
                async for chunk in self.reasoning.think_stream(
                    user_input, strategy["reasoning_mode"], context
                ):
                    response_text += chunk
                    yield chunk

            else:
                # Direct agent dispatch
                async for chunk in self.orchestrator.run_stream(user_input, session_id, context):
                    if chunk.startswith("[AGENT:"):
                        agent_role = chunk[7:chunk.index("]")]
                        yield chunk
                        continue
                    response_text += chunk
                    yield chunk

            self._success_count += 1

        except Exception as e:
            log.error(f"Meta-agent error: {e}")
            # Fallback: try capability expansion
            if self.capability and "tool" in str(e).lower():
                yield f"\n[Attempting capability expansion…]\n"
                gap_result = await self.capability.auto_expand(user_input, str(e))
                if gap_result and gap_result.get("success"):
                    yield f"\n✅ New capability created: `{gap_result['tool_name']}`\n"
                    yield f"Retry your request — new tool is now available.\n"
                else:
                    yield f"\n[ERROR: {e}]\n"
            else:
                yield f"\n[ERROR: {e}]\n"

        # 3. Persist to memory
        if response_text:
            await self.memory.save(
                f"User: {user_input}\nAssistant: {response_text}",
                {"session_id": session_id, "type": "conversation",
                 "strategy": strategy["strategy"]},
            )

        # 4. Background learning
        duration = time.time() - start
        asyncio.create_task(self._learn_and_log(
            user_input, response_text, strategy, agent_role, duration, session_id
        ))

    # ── Non-streaming ─────────────────────────────────────────────────────────
    async def run(self, user_input: str, session_id: str = "default") -> Dict:
        full = ""
        strategy_used = {}
        async for chunk in self.run_stream(user_input, session_id):
            if chunk.startswith("[META:"):
                parts = chunk[6:chunk.index("]")].split(":")
                strategy_used = {"strategy": parts[0].lower(), "complexity": parts[1].lower() if len(parts) > 1 else "?"}
                continue
            if not chunk.startswith("[AGENT:"):
                full += chunk
        return {"response": full, "strategy": strategy_used}

    # ── Context Builder ───────────────────────────────────────────────────────
    async def _build_context(self, query: str, session_id: str) -> str:
        parts = []

        # Vector memory
        memories = await self.memory.search(query, n=4)
        if memories:
            parts.append("[RELEVANT MEMORY]")
            for m in memories:
                parts.append(f"- {m['text'][:200]}")

        # Skill injection
        relevant_skills = await self.skills.get_relevant_skills(query, n=2)
        if relevant_skills:
            parts.append(self.skills.format_skills_for_prompt(relevant_skills))

        return "\n".join(parts)

    # ── Strategy Router ───────────────────────────────────────────────────────
    async def _route(self, user_input: str) -> Dict:
        raw = await self.llm.complete(
            f"User request: {user_input}",
            role="general",
            system=META_ROUTER_SYSTEM,
            temperature=0.1,
        )
        import re
        raw = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(raw)
        except Exception:
            # Safe default
            word_count = len(user_input.split())
            complexity = "complex" if word_count > 30 else "simple"
            return {
                "strategy": "plan" if word_count > 30 else "direct",
                "complexity": complexity,
                "needs_tools": False,
                "reasoning_mode": "cot",
                "estimated_steps": 1,
                "rationale": "fallback routing",
            }

    # ── Background Learning ───────────────────────────────────────────────────
    async def _learn_and_log(
        self, user_input, response, strategy, agent_role, duration, session_id
    ):
        """Fire-and-forget: learn from this interaction and log to evolution ledger."""
        try:
            # Score estimation (heuristic: longer coherent responses score higher)
            score = min(10.0, 5.0 + len(response) / 500)

            # Learn skill if good interaction
            if score >= 6.0:
                await self.skills.learn_from_interaction(
                    task=user_input,
                    response=response,
                    agent_role=agent_role,
                    score=score,
                    session_id=session_id,
                )

            # Write to evolution log (JSONL)
            entry = {
                "timestamp": time.time(),
                "session_id": session_id,
                "input_len": len(user_input),
                "response_len": len(response),
                "strategy": strategy.get("strategy"),
                "complexity": strategy.get("complexity"),
                "agent_role": agent_role,
                "duration_s": round(duration, 2),
                "score_est": round(score, 1),
                "request_n": self._request_count,
                "success_rate": round(self._success_count / max(self._request_count, 1), 2),
            }
            with open(EVOLUTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")

        except Exception as e:
            log.debug(f"Background learn error: {e}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        history = []
        try:
            if EVOLUTION_LOG.exists():
                lines = EVOLUTION_LOG.read_text().strip().split("\n")
                history = [json.loads(l) for l in lines[-20:] if l.strip()]
        except Exception:
            pass

        return {
            "total_requests": self._request_count,
            "success_count": self._success_count,
            "success_rate": round(self._success_count / max(self._request_count, 1), 2),
            "recent_history": history[-5:],
        }

    def evolution_log(self, limit: int = 50) -> list:
        try:
            if not EVOLUTION_LOG.exists():
                return []
            lines = EVOLUTION_LOG.read_text().strip().split("\n")
            return [json.loads(l) for l in lines[-limit:] if l.strip()]
        except Exception:
            return []
