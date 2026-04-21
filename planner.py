"""
Planner — Multi-Step Task Execution
Decomposes complex tasks, executes subtasks in order, aggregates results.
Integrates with AgentOrchestrator, SkillLibrary, and CapabilityEngine.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

log = logging.getLogger("synapse.planner")

PLANNER_SYSTEM = """You are an expert task planner for an AI multi-agent system.
Analyze the user's goal and create an EXECUTION PLAN.

Available agents:
- architect: system design, architecture planning
- coder: code writing, implementation
- analyzer: debugging, code review, optimization
- researcher: information gathering, explanation

Available tools: {tools}

Output ONLY valid JSON:
{{
  "goal": "one-line summary",
  "complexity": "simple|moderate|complex",
  "plan": [
    {{
      "step": 1,
      "description": "what this step does",
      "agent": "agent_name",
      "tool": "tool_name_or_null",
      "tool_params": {{}},
      "depends_on": [],
      "output_key": "result_key_name"
    }}
  ],
  "expected_output": "description of final result"
}}

Keep plans minimal — max 6 steps for complex tasks, 1-2 for simple ones."""

AGGREGATOR_SYSTEM = """You are a result aggregator.
Given a multi-step plan and its results, synthesize a clear, coherent final answer.
Be concise. Reference specific results from each step where relevant."""


@dataclass
class StepResult:
    step: int
    description: str
    agent: str
    output: str
    tool_result: Optional[Dict] = None
    success: bool = True
    duration: float = 0.0
    error: str = ""


@dataclass
class PlanResult:
    goal: str
    complexity: str
    steps_completed: int
    steps_total: int
    step_results: List[StepResult] = field(default_factory=list)
    final_answer: str = ""
    success: bool = True
    total_duration: float = 0.0


class Planner:
    def __init__(self, llm, orchestrator, tool_registry):
        self.llm = llm
        self.orchestrator = orchestrator
        self.tools = tool_registry

    # ── Main Entry ────────────────────────────────────────────────────────────
    async def execute(
        self,
        goal: str,
        context: str = "",
        session_id: str = "default",
    ) -> PlanResult:
        """Full plan-and-execute cycle."""
        start = time.time()

        # 1. Create plan
        plan_data = await self._create_plan(goal, context)
        steps = plan_data.get("plan", [])
        complexity = plan_data.get("complexity", "simple")

        log.info(f"Plan created: {len(steps)} steps, complexity={complexity}")

        result = PlanResult(
            goal=plan_data.get("goal", goal),
            complexity=complexity,
            steps_completed=0,
            steps_total=len(steps),
        )

        # 2. Execute steps
        step_outputs: Dict[str, str] = {"__context__": context}

        for step_def in steps:
            step_num = step_def.get("step", 0)
            description = step_def.get("description", "")
            agent = step_def.get("agent", "coder")
            tool_name = step_def.get("tool")
            tool_params = step_def.get("tool_params", {})
            output_key = step_def.get("output_key", f"step_{step_num}")

            log.info(f"Executing step {step_num}: {description} [{agent}]")
            step_start = time.time()

            try:
                if tool_name:
                    # Resolve param templates from previous outputs
                    resolved_params = self._resolve_params(tool_params, step_outputs)
                    tool_result = await self.tools.execute(tool_name, resolved_params)
                    output = (
                        tool_result.get("stdout", "")
                        or tool_result.get("content", "")
                        or tool_result.get("result", "")
                        or json.dumps(tool_result)
                    )
                    step_result = StepResult(
                        step=step_num,
                        description=description,
                        agent=agent,
                        output=str(output)[:3000],
                        tool_result=tool_result,
                        success=tool_result.get("success", True),
                        duration=time.time() - step_start,
                    )
                else:
                    # Build enhanced prompt with previous outputs
                    enhanced_prompt = self._build_step_prompt(description, step_outputs, goal)
                    response = await self.orchestrator.run(
                        enhanced_prompt, session_id, context
                    )
                    output = response.get("response", "")
                    step_result = StepResult(
                        step=step_num,
                        description=description,
                        agent=response.get("role", agent),
                        output=output,
                        success=True,
                        duration=time.time() - step_start,
                    )

                step_outputs[output_key] = step_result.output
                result.step_results.append(step_result)
                result.steps_completed += 1

                if not step_result.success:
                    log.warning(f"Step {step_num} failed but continuing…")

            except Exception as e:
                log.error(f"Step {step_num} error: {e}")
                step_result = StepResult(
                    step=step_num,
                    description=description,
                    agent=agent,
                    output="",
                    success=False,
                    error=str(e),
                    duration=time.time() - step_start,
                )
                result.step_results.append(step_result)

        # 3. Aggregate final answer
        result.final_answer = await self._aggregate(goal, result.step_results)
        result.total_duration = time.time() - start
        result.success = result.steps_completed > 0
        return result

    # ── Streaming Execute ─────────────────────────────────────────────────────
    async def execute_stream(
        self,
        goal: str,
        context: str = "",
        session_id: str = "default",
    ) -> AsyncGenerator[str, None]:
        """Stream planning + execution progress."""
        yield f"[PLAN] Analyzing goal…\n"

        plan_data = await self._create_plan(goal, context)
        steps = plan_data.get("plan", [])

        yield f"[PLAN] {len(steps)} steps — {plan_data.get('complexity', '?')} task\n\n"

        step_outputs: Dict[str, str] = {"__context__": context}

        for step_def in steps:
            step_num = step_def.get("step", 0)
            description = step_def.get("description", "")
            agent = step_def.get("agent", "coder")
            tool_name = step_def.get("tool")
            tool_params = step_def.get("tool_params", {})
            output_key = step_def.get("output_key", f"step_{step_num}")

            yield f"\n**Step {step_num}: {description}** `[{agent}]`\n"

            if tool_name:
                yield f"→ Running tool: `{tool_name}`…\n"
                resolved_params = self._resolve_params(tool_params, step_outputs)
                tool_result = await self.tools.execute(tool_name, resolved_params)
                output = (
                    tool_result.get("stdout", "")
                    or tool_result.get("content", "")
                    or json.dumps(tool_result, indent=2)
                )
                yield f"```\n{str(output)[:800]}\n```\n"
                step_outputs[output_key] = str(output)[:3000]
            else:
                enhanced_prompt = self._build_step_prompt(description, step_outputs, goal)
                step_output = ""
                async for chunk in self.orchestrator.run_stream(enhanced_prompt, session_id, context):
                    if chunk.startswith("[AGENT:"):
                        continue
                    step_output += chunk
                    yield chunk
                step_outputs[output_key] = step_output[:3000]

        yield f"\n\n**Synthesizing results…**\n\n"
        final = await self._aggregate(goal, [])

        # Build final answer from step_outputs
        summary_prompt = (
            f"Goal: {goal}\n\nStep outputs:\n"
            + "\n".join(f"- {k}: {v[:500]}" for k, v in step_outputs.items() if k != "__context__")
            + "\n\nSynthesize a clear final answer:"
        )
        async for chunk in self.llm.stream(summary_prompt, role="general", system=AGGREGATOR_SYSTEM):
            yield chunk

    # ── Create Plan ───────────────────────────────────────────────────────────
    async def _create_plan(self, goal: str, context: str) -> Dict:
        tool_list = ", ".join(self.tools._tools.keys())
        system = PLANNER_SYSTEM.format(tools=tool_list)
        prompt = (
            f"Goal: {goal}"
            + (f"\n\nContext: {context[:500]}" if context else "")
        )
        raw = await self.llm.complete(prompt, role="general", system=system, temperature=0.2)
        import re
        raw = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(raw)
        except Exception:
            # Fallback: single step
            return {
                "goal": goal,
                "complexity": "simple",
                "plan": [{"step": 1, "description": goal, "agent": "coder",
                          "tool": None, "tool_params": {}, "depends_on": [],
                          "output_key": "result"}],
                "expected_output": "Direct response",
            }

    # ── Aggregate Results ─────────────────────────────────────────────────────
    async def _aggregate(self, goal: str, step_results: List[StepResult]) -> str:
        if not step_results:
            return ""
        summary = "\n".join(
            f"Step {r.step} ({r.agent}): {r.output[:500]}" for r in step_results
        )
        prompt = f"Goal: {goal}\n\nResults:\n{summary}\n\nFinal synthesis:"
        return await self.llm.complete(prompt, role="general", system=AGGREGATOR_SYSTEM)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _resolve_params(self, params: Dict, outputs: Dict) -> Dict:
        """Replace {{output_key}} templates in params with actual values."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str):
                for out_key, out_val in outputs.items():
                    v = v.replace(f"{{{{{out_key}}}}}", str(out_val))
            resolved[k] = v
        return resolved

    def _build_step_prompt(self, description: str, outputs: Dict, goal: str) -> str:
        parts = [f"Overall goal: {goal}", f"\nCurrent step: {description}"]
        relevant = {k: v[:300] for k, v in outputs.items() if k != "__context__" and v}
        if relevant:
            parts.append("\nPrevious step results:")
            for k, v in relevant.items():
                parts.append(f"  [{k}]: {v}")
        return "\n".join(parts)
