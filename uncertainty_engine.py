"""
Uncertainty Engine — Calibrated Confidence & Epistemic Awareness
Makes the AI know WHAT it knows, HOW confident it is, and WHY.
Separates epistemic uncertainty (lack of knowledge) from
aleatoric uncertainty (inherent randomness).
Implements: confidence calibration, self-doubt scoring, knowledge boundary detection.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Tuple

log = logging.getLogger("synapse.uncertainty")

CALIBRATION_SYSTEM = """You are a confidence calibration expert.
Analyze your own knowledge about the given question.
Be honest about uncertainty. Distinguish between what you know vs what you're guessing.

Return ONLY valid JSON:
{
  "confidence": 0.0-1.0,
  "confidence_label": "very_high|high|medium|low|very_low|unknown",
  "epistemic_uncertainty": 0.0-1.0,
  "aleatoric_uncertainty": 0.0-1.0,
  "knowledge_sources": ["where this knowledge comes from"],
  "knowledge_gaps": ["what I don't know"],
  "assumptions": ["assumptions I'm making"],
  "potential_errors": ["ways I could be wrong"],
  "recommended_verification": ["how to verify this"],
  "answer_stability": "stable|might_change_with_context|highly_context_dependent"
}"""

DOUBT_SYSTEM = """You are a self-doubt engine for an AI system.
Given a previous answer, critically examine it for potential errors.
Be thorough but fair. Return a structured critique.

Return ONLY valid JSON:
{
  "issues_found": ["specific issue 1", "issue 2"],
  "confidence_in_answer": 0.0-1.0,
  "parts_i_am_unsure_about": ["specific uncertain part"],
  "what_could_make_this_wrong": ["condition X would invalidate this"],
  "better_answer_possible": true/false,
  "how_to_improve": "specific improvement suggestion",
  "overall_quality": 0.0-1.0
}"""

KNOWLEDGE_BOUNDARY_SYSTEM = """You are a knowledge boundary detector.
Determine if a question falls within, near, or beyond your reliable knowledge.

Return ONLY valid JSON:
{
  "domain": "domain of knowledge",
  "boundary_status": "core_knowledge|peripheral|uncertain_territory|beyond_knowledge|time_sensitive",
  "cutoff_concern": true/false,
  "hallucination_risk": "low|medium|high|very_high",
  "recommendation": "answer_confidently|answer_with_caveat|refuse_and_explain|ask_for_clarification",
  "caveat": "what caveat to add if any",
  "reason": "why this boundary status"
}"""

SOCRATIC_SYSTEM = """You are a Socratic questioning engine.
Your job is NOT to answer — your job is to identify the best clarifying questions
that would help give a much better, more precise answer.

Given a question/request, identify:
1. Ambiguities that need resolving
2. Missing context that would change the answer
3. Hidden assumptions to surface
4. Scope clarifications needed

Return ONLY valid JSON:
{
  "clarity_score": 0.0-1.0,
  "needs_clarification": true/false,
  "questions": [
    {
      "question": "clarifying question",
      "why_needed": "how this changes the answer",
      "priority": "critical|important|nice_to_have"
    }
  ],
  "assumptions_made": ["assumption if proceeding without answer"],
  "proceed_anyway": true/false
}"""


@dataclass
class UncertaintyReport:
    question:               str
    confidence:             float
    confidence_label:       str
    epistemic_uncertainty:  float
    aleatoric_uncertainty:  float
    knowledge_gaps:         List[str]
    assumptions:            List[str]
    potential_errors:       List[str]
    boundary_status:        str
    hallucination_risk:     str
    recommendation:         str
    caveat:                 str
    timestamp:              float = field(default_factory=time.time)


class UncertaintyEngine:
    def __init__(self, llm):
        self.llm = llm
        self._calibration_history: List[Dict] = []

    # ── Assess confidence before answering ───────────────────────────────────
    async def assess(self, question: str) -> UncertaintyReport:
        """Assess AI's confidence and knowledge boundary before answering."""
        # Parallel: calibration + boundary detection
        calib_task    = self.llm.complete(
            f"Question: {question}\nAssess your knowledge confidence:",
            role="general", system=CALIBRATION_SYSTEM, temperature=0.1
        )
        boundary_task = self.llm.complete(
            f"Question: {question}\nDetermine knowledge boundary:",
            role="general", system=KNOWLEDGE_BOUNDARY_SYSTEM, temperature=0.1
        )
        calib_raw, boundary_raw = await asyncio.gather(calib_task, boundary_task)

        calib, boundary = {}, {}
        try:
            calib = json.loads(re.sub(r"```json|```", "", calib_raw).strip())
        except Exception: pass
        try:
            boundary = json.loads(re.sub(r"```json|```", "", boundary_raw).strip())
        except Exception: pass

        report = UncertaintyReport(
            question=question,
            confidence=float(calib.get("confidence", 0.5)),
            confidence_label=calib.get("confidence_label", "medium"),
            epistemic_uncertainty=float(calib.get("epistemic_uncertainty", 0.3)),
            aleatoric_uncertainty=float(calib.get("aleatoric_uncertainty", 0.1)),
            knowledge_gaps=calib.get("knowledge_gaps", []),
            assumptions=calib.get("assumptions", []),
            potential_errors=calib.get("potential_errors", []),
            boundary_status=boundary.get("boundary_status", "uncertain_territory"),
            hallucination_risk=boundary.get("hallucination_risk", "medium"),
            recommendation=boundary.get("recommendation", "answer_with_caveat"),
            caveat=boundary.get("caveat", ""),
        )

        self._calibration_history.append({
            "question": question[:100],
            "confidence": report.confidence,
            "boundary": report.boundary_status,
            "timestamp": time.time(),
        })

        return report

    # ── Self-doubt: critique an answer ────────────────────────────────────────
    async def self_doubt(self, question: str, answer: str) -> Dict:
        """Critically examine a previously generated answer."""
        prompt = (
            f"Question: {question}\n\n"
            f"Answer to examine:\n{answer[:1500]}\n\n"
            f"Critically examine this answer:"
        )
        raw = await self.llm.complete(
            prompt, role="general",
            system=DOUBT_SYSTEM, temperature=0.3
        )
        try:
            return json.loads(re.sub(r"```json|```", "", raw).strip())
        except Exception:
            return {
                "issues_found": [],
                "confidence_in_answer": 0.7,
                "overall_quality": 0.7,
                "better_answer_possible": False,
                "how_to_improve": "No specific improvements identified",
            }

    # ── Socratic clarification ────────────────────────────────────────────────
    async def socratic_check(self, request: str) -> Dict:
        """Check if clarification is needed before proceeding."""
        raw = await self.llm.complete(
            f"User request: {request}\nIdentify clarifications needed:",
            role="general", system=SOCRATIC_SYSTEM, temperature=0.2
        )
        try:
            return json.loads(re.sub(r"```json|```", "", raw).strip())
        except Exception:
            return {
                "clarity_score": 0.7,
                "needs_clarification": False,
                "questions": [],
                "proceed_anyway": True,
            }

    # ── Uncertainty-aware answer ──────────────────────────────────────────────
    async def answer_with_uncertainty(
        self,
        question: str,
        context: str = "",
    ) -> AsyncGenerator[str, None]:
        """Full pipeline: assess → check boundary → answer → self-doubt."""
        # 1. Assess confidence upfront
        report = await self.assess(question)

        # 2. Yield uncertainty badge
        badge = {
            "very_high": "🟢 High confidence",
            "high":      "🟢 Good confidence",
            "medium":    "🟡 Moderate confidence",
            "low":       "🟠 Low confidence",
            "very_low":  "🔴 Very uncertain",
            "unknown":   "⬛ Unknown territory",
        }.get(report.confidence_label, "🟡 Uncertain")

        risk_flag = {
            "low": "", "medium": "",
            "high": " ⚠️ hallucination risk",
            "very_high": " 🚨 HIGH hallucination risk",
        }.get(report.hallucination_risk, "")

        yield f"[{badge}{risk_flag}] confidence={report.confidence:.0%}\n\n"

        # 3. Add caveat if needed
        if report.caveat:
            yield f"*Note: {report.caveat}*\n\n"

        # 4. If beyond knowledge, say so
        if report.recommendation == "refuse_and_explain":
            yield (
                f"I have very limited reliable knowledge about this.\n"
                f"Knowledge gaps: {'; '.join(report.knowledge_gaps[:3])}\n"
                f"Recommendation: Please verify with authoritative sources.\n\n"
            )
            return

        # 5. Generate answer
        answer_prompt = question + (f"\n\nContext: {context}" if context else "")
        full_answer = ""
        async for token in self.llm.stream(answer_prompt, role="general"):
            full_answer += token
            yield token

        # 6. Self-doubt pass if confidence is low
        if report.confidence < 0.6:
            yield "\n\n---\n**Self-review:**\n"
            doubt = await self.self_doubt(question, full_answer)
            if doubt.get("issues_found"):
                yield "Potential issues with the above:\n"
                for issue in doubt["issues_found"][:3]:
                    yield f"- {issue}\n"
            if doubt.get("how_to_improve") and doubt.get("better_answer_possible"):
                yield f"\n*{doubt['how_to_improve']}*\n"

        # 7. Knowledge gaps
        if report.knowledge_gaps:
            yield f"\n\n**Knowledge gaps I'm aware of:**\n"
            for gap in report.knowledge_gaps[:3]:
                yield f"- {gap}\n"

    # ── Batch calibrate ───────────────────────────────────────────────────────
    async def calibrate_batch(self, questions: List[str]) -> List[Dict]:
        """Run confidence calibration on multiple questions simultaneously."""
        tasks = [self.assess(q) for q in questions]
        import asyncio
        reports = await asyncio.gather(*tasks)
        return [asdict_report(r) for r in reports]

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        if not self._calibration_history:
            return {"total_assessed": 0}
        confs = [h["confidence"] for h in self._calibration_history]
        boundaries = {}
        for h in self._calibration_history:
            b = h["boundary"]
            boundaries[b] = boundaries.get(b, 0) + 1
        return {
            "total_assessed": len(self._calibration_history),
            "avg_confidence": round(sum(confs) / len(confs), 3),
            "low_confidence_rate": round(sum(1 for c in confs if c < 0.5) / len(confs), 3),
            "boundary_distribution": boundaries,
        }


def asdict_report(r: UncertaintyReport) -> Dict:
    return {
        "question": r.question,
        "confidence": r.confidence,
        "confidence_label": r.confidence_label,
        "epistemic_uncertainty": r.epistemic_uncertainty,
        "aleatoric_uncertainty": r.aleatoric_uncertainty,
        "knowledge_gaps": r.knowledge_gaps,
        "assumptions": r.assumptions,
        "potential_errors": r.potential_errors,
        "boundary_status": r.boundary_status,
        "hallucination_risk": r.hallucination_risk,
        "recommendation": r.recommendation,
        "caveat": r.caveat,
    }


# fix missing import
import asyncio
