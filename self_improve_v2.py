"""
Self-Improvement Loop v2 — Smarter, Deeper, More Autonomous
Adds: critic scoring, reflection, skill learning, strategy switching
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("synapse.improve2")

# ── Prompts ───────────────────────────────────────────────────────────────────
SOLVER_SYSTEM = """You are an elite software engineer solving a coding goal.
Think step by step. Write complete, runnable, production-quality code.
Output ONLY the code — no explanations, no fences, no preamble."""

CRITIC_SYSTEM = """You are a ruthless code critic. Score objectively.
Return ONLY valid JSON:
{
  "execution_success": true/false,
  "goal_achieved": true/false,
  "score": 0-10,
  "issues": ["specific issue 1", "specific issue 2"],
  "root_cause": "the fundamental problem if any",
  "fix_strategy": "specific actionable fix approach",
  "verdict": "pass|fail"
}"""

STRATEGY_SYSTEM = """You are a meta-programmer.
Given repeated failures, suggest a COMPLETELY DIFFERENT approach to solve the goal.
Return ONLY valid JSON:
{
  "new_approach": "description of fundamentally different strategy",
  "reasoning": "why previous approaches failed",
  "key_changes": ["change 1", "change 2"]
}"""

REFINER_SYSTEM = """You are a code refiner. Improve code based on specific issues.
Apply the fix_strategy exactly. Output ONLY the improved code — complete, runnable.
No fences, no explanations."""


@dataclass
class IterationV2:
    number: int
    strategy: str
    code: str
    exec_result: dict
    critique: dict
    refined: bool
    score: float
    duration: float
    approach: str = "initial"


@dataclass
class ImprovementResultV2:
    success: bool
    final_code: str
    best_score: float
    total_iterations: int
    strategy_switches: int
    iterations: List[IterationV2] = field(default_factory=list)
    summary: str = ""
    skill_extracted: bool = False
    final_approach: str = ""


class SelfImprovementV2:
    """
    Smarter improvement loop:
    1. Initial solve
    2. Execute + critique
    3. If failing: refine with specific fix
    4. If stuck: switch strategy entirely
    5. After success: extract skill for future reuse
    """

    def __init__(self, llm, tools, skill_library=None, max_iterations: int = 5):
        self.llm = llm
        self.tools = tools
        self.skills = skill_library
        self.max_iterations = max_iterations

    async def run(
        self,
        code_or_goal: str,
        language: str = "python",
        goal: str = "",
        is_goal_only: bool = False,
    ) -> Dict:
        """
        Two modes:
        - is_goal_only=True: generate code from scratch for a goal
        - is_goal_only=False: improve existing code
        """
        actual_goal = goal or "optimize and fix all bugs"
        log.info(f"Improvement v2: {self.max_iterations} max iterations, goal={actual_goal[:60]}")

        result = ImprovementResultV2(
            success=False,
            final_code=code_or_goal if not is_goal_only else "",
            best_score=0.0,
            total_iterations=0,
            strategy_switches=0,
        )

        best_code = ""
        consecutive_fails = 0
        current_approach = "initial"

        # Step 0: If goal-only, generate initial code
        if is_goal_only:
            current_code = await self._generate_initial(code_or_goal, language)
        else:
            current_code = code_or_goal

        for i in range(1, self.max_iterations + 1):
            iter_start = time.time()
            log.info(f"Iteration {i}/{self.max_iterations} [{current_approach}]")

            # Execute
            exec_result = await self.tools.execute("code_executor", {
                "code": current_code,
                "language": language,
                "timeout": 20,
            })

            # Critique
            critique = await self._critique(
                code=current_code,
                exec_result=exec_result,
                goal=actual_goal,
            )
            score = float(critique.get("score", 0))
            verdict = critique.get("verdict", "fail")

            # Track best
            if score > result.best_score:
                result.best_score = score
                best_code = current_code
                result.final_approach = current_approach

            iteration = IterationV2(
                number=i,
                strategy="improve" if not is_goal_only else "generate",
                code=current_code,
                exec_result=exec_result,
                critique=critique,
                refined=False,
                score=score,
                duration=time.time() - iter_start,
                approach=current_approach,
            )

            log.info(f"Iteration {i}: score={score}/10, verdict={verdict}")

            if verdict == "pass" or score >= 8.5:
                iteration.refined = True
                result.iterations.append(iteration)
                result.success = True
                result.final_code = current_code
                result.total_iterations = i
                result.summary = f"✅ Achieved score {score}/10 after {i} iteration(s)"
                log.info(f"🎉 SUCCESS at iteration {i}")
                break

            result.iterations.append(iteration)
            consecutive_fails += 1

            if i < self.max_iterations:
                # Decide: refine or switch strategy
                if consecutive_fails >= 2 and i <= self.max_iterations - 2:
                    # Try a completely different approach
                    log.info(f"Switching strategy after {consecutive_fails} consecutive fails")
                    new_approach_data = await self._get_new_strategy(
                        actual_goal, language, result.iterations
                    )
                    new_approach_desc = new_approach_data.get("new_approach", "")
                    if new_approach_desc:
                        current_code = await self._generate_with_approach(
                            actual_goal, language, new_approach_desc
                        )
                        current_approach = f"alt_{i}"
                        result.strategy_switches += 1
                        consecutive_fails = 0
                        iteration.refined = True
                        continue

                # Standard refinement
                refined = await self._refine(current_code, exec_result, critique, actual_goal, language)
                if refined and refined.strip():
                    current_code = refined
                    iteration.refined = True
                    consecutive_fails = 0

        if not result.success:
            result.final_code = best_code or current_code
            result.total_iterations = self.max_iterations
            result.summary = (
                f"⚠️ Best score: {result.best_score}/10 after {self.max_iterations} iterations"
            )

        # Learn from success
        if result.success and self.skills:
            try:
                skill = await self.skills.learn_from_interaction(
                    task=f"Improve code for goal: {actual_goal}",
                    response=result.final_code,
                    score=result.best_score,
                )
                result.skill_extracted = skill is not None
            except Exception as e:
                log.debug(f"Skill extraction failed: {e}")

        return self._serialize(result)

    # ── Generation ────────────────────────────────────────────────────────────
    async def _generate_initial(self, goal: str, language: str) -> str:
        prompt = f"Language: {language}\nGoal: {goal}\nWrite the complete solution:"
        code = await self.llm.complete(prompt, role="coder", system=SOLVER_SYSTEM, temperature=0.4)
        return self._strip_fences(code)

    async def _generate_with_approach(self, goal: str, language: str, approach: str) -> str:
        prompt = (
            f"Language: {language}\nGoal: {goal}\n"
            f"Approach to use: {approach}\n\nWrite complete solution using this approach:"
        )
        code = await self.llm.complete(prompt, role="coder", system=SOLVER_SYSTEM, temperature=0.5)
        return self._strip_fences(code)

    # ── Critique ──────────────────────────────────────────────────────────────
    async def _critique(self, code: str, exec_result: dict, goal: str) -> Dict:
        prompt = (
            f"Goal: {goal}\n"
            f"Code:\n{code[:2000]}\n\n"
            f"Execution:\n"
            f"  success={exec_result.get('success')}\n"
            f"  stdout={exec_result.get('stdout', '')[:800]}\n"
            f"  stderr={exec_result.get('stderr', '')[:400]}"
        )
        raw = await self.llm.complete(prompt, role="general", system=CRITIC_SYSTEM, temperature=0.1)
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            # Infer from execution result
            success = exec_result.get("success", False)
            return {
                "execution_success": success,
                "goal_achieved": success,
                "score": 6.0 if success else 2.0,
                "issues": [exec_result.get("stderr", "unknown error")],
                "root_cause": "parse_failed",
                "fix_strategy": "fix syntax and logic errors",
                "verdict": "pass" if success else "fail",
            }

    # ── Refine ────────────────────────────────────────────────────────────────
    async def _refine(self, code: str, exec_result: dict, critique: dict, goal: str, lang: str) -> str:
        fix_strategy = critique.get("fix_strategy", "fix all issues")
        issues = "\n".join(f"- {i}" for i in critique.get("issues", []))
        prompt = (
            f"Goal: {goal}\nLanguage: {lang}\n\n"
            f"Current code:\n{code}\n\n"
            f"Execution output:\n"
            f"  stdout={exec_result.get('stdout', '')[:600]}\n"
            f"  stderr={exec_result.get('stderr', '')[:400]}\n\n"
            f"Root cause: {critique.get('root_cause', '')}\n"
            f"Fix strategy: {fix_strategy}\n"
            f"Issues:\n{issues}\n\n"
            f"Write the fixed code:"
        )
        code = await self.llm.complete(prompt, role="coder", system=REFINER_SYSTEM, temperature=0.35)
        return self._strip_fences(code)

    # ── Strategy Switch ───────────────────────────────────────────────────────
    async def _get_new_strategy(
        self, goal: str, lang: str, iterations: List[IterationV2]
    ) -> Dict:
        failed_approaches = "\n".join(
            f"- Iteration {it.number}: score={it.score}/10, issue={it.critique.get('root_cause', '')}"
            for it in iterations
        )
        prompt = (
            f"Goal: {goal}\nLanguage: {lang}\n\n"
            f"Failed approaches:\n{failed_approaches}\n\n"
            f"Suggest a fundamentally different strategy:"
        )
        raw = await self.llm.complete(prompt, role="general", system=STRATEGY_SYSTEM, temperature=0.6)
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {"new_approach": f"rewrite from scratch using a simpler algorithm", "reasoning": "previous approaches all failed", "key_changes": []}

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _strip_fences(self, code: str) -> str:
        code = re.sub(r"```\w*\n?", "", code)
        return code.replace("```", "").strip()

    def _serialize(self, result: ImprovementResultV2) -> Dict:
        return {
            "success": result.success,
            "final_code": result.final_code,
            "best_score": result.best_score,
            "total_iterations": result.total_iterations,
            "strategy_switches": result.strategy_switches,
            "skill_learned": result.skill_extracted,
            "summary": result.summary,
            "approach": result.final_approach,
            "iterations": [
                {
                    "number": it.number,
                    "approach": it.approach,
                    "score": it.score,
                    "refined": it.refined,
                    "duration_s": round(it.duration, 2),
                    "execution": {
                        "success": it.exec_result.get("success"),
                        "stdout": it.exec_result.get("stdout", "")[:400],
                        "stderr": it.exec_result.get("stderr", "")[:200],
                    },
                    "critique": {
                        "root_cause": it.critique.get("root_cause"),
                        "fix_strategy": it.critique.get("fix_strategy"),
                        "issues": it.critique.get("issues", [])[:3],
                    },
                }
                for it in result.iterations
            ],
        }
