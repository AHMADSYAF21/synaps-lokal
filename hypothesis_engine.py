"""
Hypothesis Engine — Scientific Reasoning System
Generates hypotheses, designs tests, executes them, evaluates results,
and iterates toward truth. Supports: causal reasoning, counterfactuals,
abductive inference, and structured argumentation.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import AsyncGenerator, Dict, List, Optional

log = logging.getLogger("synapse.hypothesis")

HYPOTHESIS_GEN_SYSTEM = """You are a scientific hypothesis generator.
Given an observation or question, generate multiple distinct hypotheses.
Return ONLY valid JSON:
{
  "observation": "what we observe",
  "hypotheses": [
    {
      "id": "H1",
      "statement": "clear hypothesis statement",
      "type": "causal|correlational|predictive|explanatory",
      "mechanism": "proposed mechanism or explanation",
      "testable": true,
      "falsifiable": true,
      "prior_probability": 0.0-1.0,
      "test_suggestion": "how to test this"
    }
  ]
}"""

HYPOTHESIS_TEST_SYSTEM = """You are a hypothesis evaluator.
Given a hypothesis and evidence/test results, evaluate the hypothesis.
Return ONLY valid JSON:
{
  "hypothesis_id": "H1",
  "verdict": "supported|refuted|inconclusive|needs_more_evidence",
  "confidence": 0.0-1.0,
  "evidence_for": ["evidence supporting"],
  "evidence_against": ["evidence against"],
  "posterior_probability": 0.0-1.0,
  "next_test": "what to test next",
  "bayesian_update": "how this changes our beliefs"
}"""

CAUSAL_SYSTEM = """You are a causal reasoning expert.
Analyze the causal structure of the given situation.
Return ONLY valid JSON:
{
  "variables": [{"name": "X", "type": "cause|effect|confounder|mediator"}],
  "causal_links": [{"from": "X", "to": "Y", "strength": 0.0-1.0, "mechanism": "..."}],
  "confounders": ["variable that affects both X and Y"],
  "counterfactual": "what would happen if X was different",
  "intervention_suggestion": "what to change to affect Y",
  "confidence": 0.0-1.0
}"""

ABDUCTIVE_SYSTEM = """You are an abductive reasoning engine (inference to best explanation).
Given observations, infer the most likely explanation.
Rank by: simplicity, explanatory power, prior plausibility.
Return ONLY valid JSON:
{
  "observations": ["obs1", "obs2"],
  "explanations": [
    {
      "rank": 1,
      "explanation": "...",
      "explanatory_power": 0.0-1.0,
      "simplicity": 0.0-1.0,
      "plausibility": 0.0-1.0,
      "score": 0.0-1.0
    }
  ],
  "best_explanation": "...",
  "confidence": 0.0-1.0
}"""

ARGUMENT_SYSTEM = """You are a structured argumentation analyst.
Analyze the argument structure of the given text.
Return ONLY valid JSON:
{
  "claim": "main claim",
  "premises": ["premise 1", "premise 2"],
  "inference_type": "deductive|inductive|abductive",
  "validity": "valid|invalid|uncertain",
  "soundness": "sound|unsound|uncertain",
  "fallacies": ["fallacy if any"],
  "counter_arguments": ["strongest counter-argument"],
  "strength": 0.0-1.0
}"""

THOUGHT_CHAIN_SYSTEM = """You are a deliberate, step-by-step reasoner.
For EVERY step of your reasoning, explicitly state:
1. What you know
2. What you're inferring
3. How confident you are (%)
4. What could make you wrong

Format each step as:
[KNOW] ...
[INFER] ...
[CONFIDENCE] X%
[DOUBT] ...

End with:
[CONCLUSION] Your final answer
[CERTAINTY] How certain you are and why"""


@dataclass
class Hypothesis:
    h_id:              str
    statement:         str
    h_type:            str
    mechanism:         str
    testable:          bool
    falsifiable:       bool
    prior_probability: float
    test_suggestion:   str
    posterior_probability: float = 0.0
    verdict:           str = "untested"
    confidence:        float = 0.0
    evidence_for:      List[str] = field(default_factory=list)
    evidence_against:  List[str] = field(default_factory=list)
    tests_run:         int = 0


@dataclass
class HypothesisSet:
    observation:  str
    hypotheses:   List[Hypothesis]
    best_hypothesis: Optional[str] = None
    iteration:    int = 0
    concluded:    bool = False
    conclusion:   str = ""


class HypothesisEngine:
    def __init__(self, llm, tools):
        self.llm   = llm
        self.tools = tools

    # ── Main: Generate hypotheses ─────────────────────────────────────────────
    async def generate(self, observation: str, n: int = 4) -> HypothesisSet:
        """Generate multiple competing hypotheses for an observation."""
        prompt = f"Observation: {observation}\nGenerate {n} distinct testable hypotheses:"
        raw = await self.llm.complete(
            prompt, role="general",
            system=HYPOTHESIS_GEN_SYSTEM, temperature=0.7
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
            hyps = [
                Hypothesis(
                    h_id=h.get("id", f"H{i+1}"),
                    statement=h.get("statement", ""),
                    h_type=h.get("type", "explanatory"),
                    mechanism=h.get("mechanism", ""),
                    testable=h.get("testable", True),
                    falsifiable=h.get("falsifiable", True),
                    prior_probability=float(h.get("prior_probability", 0.25)),
                    test_suggestion=h.get("test_suggestion", ""),
                )
                for i, h in enumerate(data.get("hypotheses", []))
            ]
            return HypothesisSet(
                observation=observation,
                hypotheses=hyps[:n],
            )
        except Exception as e:
            log.error(f"Hypothesis generation parse error: {e}")
            return HypothesisSet(
                observation=observation,
                hypotheses=[Hypothesis(
                    h_id="H1", statement=f"Most likely explanation for: {observation}",
                    h_type="explanatory", mechanism="unknown",
                    testable=True, falsifiable=True, prior_probability=0.5,
                    test_suggestion="Gather more evidence",
                )],
            )

    # ── Test a hypothesis ─────────────────────────────────────────────────────
    async def test(
        self,
        hyp_set: HypothesisSet,
        hypothesis_id: str,
        evidence: str,
    ) -> Dict:
        """Evaluate a hypothesis against evidence."""
        hyp = next((h for h in hyp_set.hypotheses if h.h_id == hypothesis_id), None)
        if not hyp:
            return {"error": f"Hypothesis {hypothesis_id} not found"}

        prompt = (
            f"Hypothesis: {hyp.statement}\n"
            f"Mechanism: {hyp.mechanism}\n"
            f"Evidence/Test result: {evidence}\n"
            f"Prior probability: {hyp.prior_probability}\n"
            f"Evaluate:"
        )
        raw = await self.llm.complete(
            prompt, role="general",
            system=HYPOTHESIS_TEST_SYSTEM, temperature=0.2
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            result = json.loads(raw)
            # Update hypothesis
            hyp.verdict              = result.get("verdict", "inconclusive")
            hyp.confidence           = float(result.get("confidence", 0.5))
            hyp.posterior_probability = float(result.get("posterior_probability", hyp.prior_probability))
            hyp.evidence_for.extend(result.get("evidence_for", []))
            hyp.evidence_against.extend(result.get("evidence_against", []))
            hyp.tests_run += 1
            return result
        except Exception as e:
            return {"error": str(e), "verdict": "inconclusive"}

    # ── Auto-test with code execution ─────────────────────────────────────────
    async def auto_test(
        self,
        hypothesis: str,
        write_test_code: bool = True,
    ) -> Dict:
        """AI writes test code, runs it, evaluates result."""
        if not write_test_code:
            return {"error": "Code testing disabled"}

        # Ask LLM to write a test
        code_prompt = (
            f"Write Python code to test this hypothesis:\n{hypothesis}\n\n"
            f"The code should print a result that either supports or refutes the hypothesis.\n"
            f"Keep it simple and runnable. No external dependencies except stdlib."
        )
        code = await self.llm.complete(
            code_prompt, role="coder", temperature=0.3
        )
        code = re.sub(r"```python|```", "", code).strip()

        # Execute test
        result = await self.tools.execute("code_executor", {
            "code": code, "language": "python", "timeout": 15
        })

        # Evaluate result
        output = result.get("stdout", "") + result.get("stderr", "")
        eval_prompt = (
            f"Hypothesis: {hypothesis}\n"
            f"Test code output:\n{output}\n"
            f"Execution success: {result.get('success')}\n"
            f"Does this support or refute the hypothesis?"
        )
        evaluation = await self.llm.complete(
            eval_prompt, role="general",
            system=HYPOTHESIS_TEST_SYSTEM, temperature=0.1
        )
        try:
            ev = re.sub(r"```json|```", "", evaluation).strip()
            return {**json.loads(ev), "code": code, "output": output}
        except Exception:
            return {"code": code, "output": output, "verdict": "inconclusive"}

    # ── Iterate to conclusion ─────────────────────────────────────────────────
    async def iterate_stream(
        self,
        observation: str,
        max_iterations: int = 3,
    ) -> AsyncGenerator[str, None]:
        """Full hypothesis → test → update cycle, streamed."""
        yield f"**🔬 Hypothesis Engine**\n\nObservation: _{observation}_\n\n"

        hyp_set = await self.generate(observation, n=3)
        yield f"**Generated {len(hyp_set.hypotheses)} hypotheses:**\n"
        for h in hyp_set.hypotheses:
            yield f"- **{h.h_id}** (p={h.prior_probability:.0%}): {h.statement}\n"
        yield "\n"

        for iteration in range(1, max_iterations + 1):
            yield f"**── Iteration {iteration} ──**\n"

            # Sort by current posterior (or prior for first iteration)
            ranked = sorted(
                hyp_set.hypotheses,
                key=lambda h: h.posterior_probability or h.prior_probability,
                reverse=True,
            )
            top_h = ranked[0]

            yield f"Testing leading hypothesis: **{top_h.h_id}**\n"
            yield f"_{top_h.statement}_\n\n"

            # AI designs and runs a test
            test_code_prompt = (
                f"Hypothesis: {top_h.statement}\n"
                f"Test suggestion: {top_h.test_suggestion}\n\n"
                f"Write simple Python code to gather evidence about this hypothesis.\n"
                f"Use only stdlib. Print findings clearly."
            )
            code = await self.llm.complete(test_code_prompt, role="coder", temperature=0.3)
            code = re.sub(r"```python|```", "", code).strip()

            yield f"Running test…\n```python\n{code[:300]}\n```\n"

            exec_result = await self.tools.execute("code_executor", {
                "code": code, "language": "python", "timeout": 15
            })
            output = exec_result.get("stdout", "")[:500] or exec_result.get("stderr", "")[:200]
            yield f"Output: `{output}`\n\n"

            # Evaluate
            eval_result = await self.test(hyp_set, top_h.h_id, output)
            verdict    = eval_result.get("verdict", "inconclusive")
            confidence = eval_result.get("confidence", 0.5)

            yield f"Verdict: **{verdict}** (confidence: {confidence:.0%})\n"

            if eval_result.get("evidence_for"):
                yield f"Supporting evidence: {'; '.join(eval_result['evidence_for'][:2])}\n"
            if eval_result.get("bayesian_update"):
                yield f"Bayesian update: {eval_result['bayesian_update']}\n"
            yield "\n"

            # Check if we've reached a conclusion
            if verdict == "supported" and confidence > 0.75:
                hyp_set.best_hypothesis = top_h.h_id
                hyp_set.concluded = True
                hyp_set.conclusion = top_h.statement
                yield f"**✅ Conclusion reached** after {iteration} iteration(s):\n"
                yield f"**{top_h.statement}**\n"
                yield f"Confidence: {confidence:.0%}\n"
                break
            elif verdict == "refuted":
                yield f"Hypothesis {top_h.h_id} refuted. Proceeding to next hypothesis.\n\n"

        if not hyp_set.concluded:
            best = max(hyp_set.hypotheses, key=lambda h: h.posterior_probability or h.prior_probability)
            yield f"\n**⚠️ Best available explanation** (inconclusive):\n"
            yield f"{best.statement} (p={best.posterior_probability or best.prior_probability:.0%})\n"
            yield f"More evidence needed.\n"

    # ── Causal Analysis ───────────────────────────────────────────────────────
    async def causal_analysis(self, situation: str) -> Dict:
        raw = await self.llm.complete(
            f"Situation: {situation}\nAnalyze causal structure:",
            role="general", system=CAUSAL_SYSTEM, temperature=0.3
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {"error": "Could not parse causal structure"}

    # ── Abductive Inference ───────────────────────────────────────────────────
    async def abductive(self, observations: List[str]) -> Dict:
        obs_text = "\n".join(f"- {o}" for o in observations)
        raw = await self.llm.complete(
            f"Observations:\n{obs_text}\n\nInfer best explanation:",
            role="general", system=ABDUCTIVE_SYSTEM, temperature=0.4
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {"error": "Could not parse abductive inference"}

    # ── Argument Analysis ─────────────────────────────────────────────────────
    async def analyze_argument(self, argument: str) -> Dict:
        raw = await self.llm.complete(
            f"Argument to analyze:\n{argument}",
            role="general", system=ARGUMENT_SYSTEM, temperature=0.2
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {"error": "Could not parse argument structure"}

    # ── Explicit thought chain ────────────────────────────────────────────────
    async def think_explicitly(
        self, question: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """Force explicit step-by-step reasoning with confidence + doubt."""
        prompt = (
            f"{'Context: ' + context + chr(10) if context else ''}"
            f"Question: {question}\n\n"
            f"Think through this EXPLICITLY step by step:"
        )
        async for token in self.llm.stream(
            prompt, role="general",
            system=THOUGHT_CHAIN_SYSTEM, temperature=0.4
        ):
            yield token
