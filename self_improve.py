"""
Self-Improvement Loop
AI generates → executes → evaluates → refines (up to N iterations)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from core.llm import LLMService
from core.tools import ToolRegistry

log = logging.getLogger("synapse.improve")


@dataclass
class Iteration:
    number: int
    code: str
    execution_result: dict
    evaluation: str
    improved: bool
    score: float = 0.0


@dataclass
class ImprovementResult:
    success: bool
    final_code: str
    iterations: List[Iteration] = field(default_factory=list)
    total_iterations: int = 0
    improvement_summary: str = ""
    error: Optional[str] = None


EVALUATOR_PROMPT = """You are a code evaluator. Given code and its execution result, evaluate:
1. Does it run without errors? (0-3 pts)
2. Does it achieve the stated goal? (0-4 pts)
3. Is the code clean and efficient? (0-3 pts)

Respond in JSON:
{"score": <0-10>, "issues": ["issue1", ...], "suggestions": ["fix1", ...], "pass": <true/false>}
Only respond with valid JSON, nothing else."""

IMPROVER_PROMPT = """You are a code improvement expert.
Given: original code, its execution output, and evaluation feedback.
Your task: produce improved code that fixes all issues.

Rules:
- Output ONLY the improved code, no explanations
- No markdown code fences
- Must be complete, runnable code"""


class SelfImprovementLoop:
    def __init__(self, llm: LLMService, tools: ToolRegistry, max_iterations: int = 3):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations

    async def run(self, code: str, language: str = "python", goal: str = "fix and optimize") -> dict:
        """Main improvement loop."""
        log.info(f"Starting improvement loop: {self.max_iterations} max iterations")
        result = ImprovementResult(success=False, final_code=code)

        current_code = code

        for i in range(1, self.max_iterations + 1):
            log.info(f"Iteration {i}/{self.max_iterations}")

            # Step 1: Execute code
            exec_result = await self.tools.execute("code_executor", {
                "code": current_code,
                "language": language,
                "timeout": 15,
            })

            # Step 2: Evaluate
            evaluation_raw = await self._evaluate(current_code, exec_result, goal, language)
            try:
                evaluation = json.loads(evaluation_raw)
            except Exception:
                evaluation = {"score": 0, "issues": [evaluation_raw], "suggestions": [], "pass": False}

            score = float(evaluation.get("score", 0))
            passed = evaluation.get("pass", False) or score >= 8.0

            iteration = Iteration(
                number=i,
                code=current_code,
                execution_result=exec_result,
                evaluation=json.dumps(evaluation, indent=2),
                improved=False,
                score=score,
            )

            log.info(f"Iteration {i} score: {score}/10, pass={passed}")

            if passed:
                iteration.improved = True
                result.iterations.append(iteration)
                result.success = True
                result.final_code = current_code
                result.total_iterations = i
                result.improvement_summary = (
                    f"✅ Passed after {i} iteration(s) with score {score}/10"
                )
                log.info(f"🎉 Passed at iteration {i}")
                break

            # Step 3: Improve if not last iteration
            if i < self.max_iterations:
                improved_code = await self._improve(
                    current_code, exec_result, evaluation, goal, language
                )
                if improved_code and improved_code.strip() != current_code.strip():
                    iteration.improved = True
                    current_code = improved_code
                result.iterations.append(iteration)
            else:
                result.iterations.append(iteration)
                # Even if not passing, return best version
                result.final_code = current_code
                result.total_iterations = i
                result.improvement_summary = (
                    f"⚠️ Completed {i} iteration(s). Final score: {score}/10"
                )

        if not result.success and result.total_iterations == 0:
            result.total_iterations = self.max_iterations
            result.improvement_summary = "❌ Could not improve within iteration limit"

        return {
            "success": result.success,
            "final_code": result.final_code,
            "total_iterations": result.total_iterations,
            "summary": result.improvement_summary,
            "iterations": [
                {
                    "number": it.number,
                    "score": it.score,
                    "improved": it.improved,
                    "execution": {
                        "success": it.execution_result.get("success"),
                        "stdout": it.execution_result.get("stdout", "")[:500],
                        "stderr": it.execution_result.get("stderr", "")[:500],
                    },
                    "evaluation": it.evaluation,
                }
                for it in result.iterations
            ],
        }

    async def _evaluate(self, code: str, exec_result: dict, goal: str, lang: str) -> str:
        prompt = (
            f"Goal: {goal}\n"
            f"Language: {lang}\n\n"
            f"Code:\n{code}\n\n"
            f"Execution Result:\n"
            f"  success={exec_result.get('success')}\n"
            f"  stdout={exec_result.get('stdout', '')[:1000]}\n"
            f"  stderr={exec_result.get('stderr', '')[:500]}\n"
        )
        return await self.llm.complete(prompt, role="general", system=EVALUATOR_PROMPT, temperature=0.1)

    async def _improve(self, code: str, exec_result: dict, evaluation: dict, goal: str, lang: str) -> str:
        issues = "\n".join(f"- {i}" for i in evaluation.get("issues", []))
        suggestions = "\n".join(f"- {s}" for s in evaluation.get("suggestions", []))

        prompt = (
            f"Goal: {goal}\n"
            f"Language: {lang}\n\n"
            f"Original code:\n{code}\n\n"
            f"Execution output:\n"
            f"  stdout={exec_result.get('stdout', '')[:500]}\n"
            f"  stderr={exec_result.get('stderr', '')[:500]}\n\n"
            f"Issues found:\n{issues}\n\n"
            f"Suggested fixes:\n{suggestions}\n\n"
            f"Provide the improved code:"
        )
        improved = await self.llm.complete(prompt, role="coder", system=IMPROVER_PROMPT, temperature=0.4)
        # Strip code fences if model adds them anyway
        improved = improved.strip()
        for fence in ["```python", "```javascript", "```js", "```"]:
            improved = improved.replace(fence, "")
        return improved.strip()
