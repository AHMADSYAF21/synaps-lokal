"""
Reasoning Engine — Advanced Thinking Strategies
Implements: Chain-of-Thought, Tree-of-Thought, ReAct, Reflection
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, List, Optional, Dict, Any

from core.llm import LLMService

log = logging.getLogger("synapse.reasoning")


# ── Prompts ───────────────────────────────────────────────────────────────────
COT_SYSTEM = """You are an advanced reasoning engine.
When solving problems, ALWAYS use step-by-step chain-of-thought reasoning.
Format:
<think>
Step 1: [first reasoning step]
Step 2: [next step]
...
Conclusion: [final answer]
</think>
<answer>[clear, concise final answer]</answer>"""

TOT_SYSTEM = """You are a tree-of-thought reasoning engine.
Generate MULTIPLE solution branches, evaluate each, then pick the best.
Format:
<branch id="1">[approach 1 reasoning]</branch>
<eval id="1">score: X/10, reason: [why]</eval>
<branch id="2">[approach 2 reasoning]</branch>
<eval id="2">score: X/10, reason: [why]</eval>
<best>[ID of best branch and why]</best>
<answer>[solution based on best branch]</answer>"""

REFLECTION_SYSTEM = """You are a self-reflective AI.
Given a task and a previous response, critically evaluate:
1. What was done well?
2. What was wrong or incomplete?
3. What would you do differently?
4. Produce an improved response.

Format:
<reflection>
strengths: [what worked]
weaknesses: [what failed]  
improvement: [what to change]
</reflection>
<improved>[better response here]</improved>"""

CRITIC_SYSTEM = """You are a harsh but fair code and reasoning critic.
Score the given response on:
- Correctness (0-10)
- Completeness (0-10)  
- Efficiency (0-10)
- Safety (0-10)

Return ONLY valid JSON:
{"correctness": N, "completeness": N, "efficiency": N, "safety": N, 
 "overall": N, "issues": ["..."], "verdict": "pass|fail"}"""

DECOMPOSE_SYSTEM = """You are a task decomposition expert.
Break complex tasks into ordered, concrete subtasks.
Return ONLY valid JSON:
{
  "complexity": "simple|moderate|complex",
  "subtasks": [
    {"id": 1, "task": "...", "depends_on": [], "agent": "architect|coder|analyzer|researcher"},
    ...
  ],
  "estimated_steps": N
}"""


@dataclass
class ThoughtNode:
    id: str
    content: str
    score: float = 0.0
    children: List["ThoughtNode"] = field(default_factory=list)


@dataclass 
class ReasoningResult:
    strategy: str
    raw_output: str
    answer: str
    thinking: str = ""
    score: float = 0.0
    reflection: str = ""
    improved: bool = False


class ReasoningEngine:
    def __init__(self, llm: LLMService):
        self.llm = llm

    # ── Strategy Router ───────────────────────────────────────────────────────
    async def think(
        self,
        task: str,
        strategy: str = "auto",
        context: str = "",
        role: str = "general",
    ) -> ReasoningResult:
        """
        Route to best reasoning strategy:
        auto → picks strategy based on task complexity
        cot  → Chain of Thought
        tot  → Tree of Thought (multi-branch)
        react→ Reason + Act (tool-aware)
        """
        if strategy == "auto":
            strategy = await self._pick_strategy(task)
            log.info(f"Auto-selected reasoning strategy: {strategy}")

        if strategy == "tot":
            return await self._tree_of_thought(task, context, role)
        elif strategy == "reflect":
            return await self._reflect(task, context, role)
        else:
            return await self._chain_of_thought(task, context, role)

    async def think_stream(
        self,
        task: str,
        strategy: str = "auto",
        context: str = "",
        role: str = "general",
    ) -> AsyncGenerator[str, None]:
        """Streaming version — yields tokens + thinking markers."""
        if strategy == "auto":
            strategy = await self._pick_strategy(task)

        prompt = self._build_cot_prompt(task, context)
        system = COT_SYSTEM if strategy == "cot" else TOT_SYSTEM

        yield f"[THINKING:{strategy.upper()}]\n"
        full = ""
        async for token in self.llm.stream(prompt, role=role, system=system):
            full += token
            # Show thinking in real-time
            yield token

        # Extract clean answer
        answer = self._extract_answer(full)
        if answer and answer != full:
            yield f"\n[ANSWER]\n{answer}"

    # ── Chain of Thought ──────────────────────────────────────────────────────
    async def _chain_of_thought(self, task: str, context: str, role: str) -> ReasoningResult:
        prompt = self._build_cot_prompt(task, context)
        raw = await self.llm.complete(prompt, role=role, system=COT_SYSTEM)
        thinking = self._extract_tag(raw, "think")
        answer = self._extract_tag(raw, "answer") or raw
        return ReasoningResult(
            strategy="cot",
            raw_output=raw,
            thinking=thinking,
            answer=answer,
        )

    # ── Tree of Thought ───────────────────────────────────────────────────────
    async def _tree_of_thought(self, task: str, context: str, role: str) -> ReasoningResult:
        prompt = (
            f"Problem to solve with multiple approaches:\n{task}"
            + (f"\n\nContext: {context}" if context else "")
        )
        raw = await self.llm.complete(prompt, role=role, system=TOT_SYSTEM, temperature=0.8)
        answer = self._extract_tag(raw, "answer") or raw
        best = self._extract_tag(raw, "best") or ""

        # Parse scores
        scores = re.findall(r'score:\s*(\d+)/10', raw)
        avg_score = sum(int(s) for s in scores) / len(scores) if scores else 5.0

        return ReasoningResult(
            strategy="tot",
            raw_output=raw,
            thinking=best,
            answer=answer,
            score=avg_score,
        )

    # ── Self-Reflection ───────────────────────────────────────────────────────
    async def _reflect(self, task: str, context: str, role: str) -> ReasoningResult:
        # Step 1: Initial response
        initial = await self.llm.complete(task + (f"\n{context}" if context else ""), role=role)

        # Step 2: Reflect and improve
        reflection_prompt = (
            f"Original task: {task}\n\nPrevious response:\n{initial}\n\nReflect and improve:"
        )
        raw = await self.llm.complete(
            reflection_prompt, role=role, system=REFLECTION_SYSTEM, temperature=0.5
        )

        reflection = self._extract_tag(raw, "reflection")
        improved = self._extract_tag(raw, "improved") or raw

        return ReasoningResult(
            strategy="reflect",
            raw_output=raw,
            thinking=reflection,
            answer=improved,
            improved=True,
        )

    # ── Critic ────────────────────────────────────────────────────────────────
    async def critique(self, task: str, response: str) -> Dict[str, Any]:
        """Score a response — used by self-improvement loop."""
        prompt = f"Task:\n{task}\n\nResponse to evaluate:\n{response}"
        raw = await self.llm.complete(prompt, role="general", system=CRITIC_SYSTEM, temperature=0.1)
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {
                "correctness": 5, "completeness": 5, "efficiency": 5, "safety": 8,
                "overall": 5, "issues": ["Could not parse critique"], "verdict": "fail"
            }

    # ── Task Decomposition ────────────────────────────────────────────────────
    async def decompose(self, task: str) -> Dict[str, Any]:
        """Break complex task into ordered subtasks."""
        raw = await self.llm.complete(
            f"Decompose this task into subtasks:\n{task}",
            role="general",
            system=DECOMPOSE_SYSTEM,
            temperature=0.2,
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            # Fallback: single task
            return {
                "complexity": "simple",
                "subtasks": [{"id": 1, "task": task, "depends_on": [], "agent": "coder"}],
                "estimated_steps": 1,
            }

    # ── Strategy Picker ───────────────────────────────────────────────────────
    async def _pick_strategy(self, task: str) -> str:
        PICKER_PROMPT = """Classify task reasoning need.
        Reply with ONE word only: cot | tot | reflect
        - cot: straightforward tasks, code writing, explanations
        - tot: complex problems with multiple valid approaches
        - reflect: tasks needing self-correction or critique"""

        result = await self.llm.complete(
            f"Task: {task}",
            role="general",
            system=PICKER_PROMPT,
            temperature=0.1,
        )
        word = result.strip().lower().split()[0] if result.strip() else "cot"
        return word if word in ("cot", "tot", "reflect") else "cot"

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _build_cot_prompt(self, task: str, context: str) -> str:
        parts = []
        if context:
            parts.append(f"[Context]\n{context}\n")
        parts.append(f"Task: {task}")
        return "\n".join(parts)

    def _extract_tag(self, text: str, tag: str) -> str:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_answer(self, text: str) -> str:
        return self._extract_tag(text, "answer") or text
