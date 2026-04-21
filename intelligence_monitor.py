"""
Intelligence Monitor — Track, Measure & Visualize AI Intelligence Growth
Monitors: reasoning quality, knowledge breadth, skill acquisition rate,
response consistency, self-correction rate, task success rate.
Produces intelligence profiles and growth curves.
"""

import json
import logging
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("synapse.intel_monitor")

INTEL_DB = Path("./data/intelligence_monitor.db")
INTEL_DB.parent.mkdir(parents=True, exist_ok=True)

# Intelligence dimensions
DIMENSIONS = {
    "reasoning":     "Logical reasoning and problem-solving quality",
    "knowledge":     "Breadth and accuracy of domain knowledge",
    "creativity":    "Ability to generate novel, useful solutions",
    "precision":     "Accuracy and correctness of responses",
    "adaptability":  "Ability to handle diverse task types",
    "meta_learning": "Rate of acquiring new skills and capabilities",
    "consistency":   "Stability and reliability across similar queries",
    "self_awareness": "Accuracy in assessing own uncertainty",
}

EVAL_SYSTEM = """You are an AI intelligence evaluator.
Evaluate the given AI response on multiple intelligence dimensions.
Be objective and calibrated — don't inflate or deflate scores.
Return ONLY valid JSON:
{
  "reasoning": 0.0-10.0,
  "knowledge": 0.0-10.0,
  "creativity": 0.0-10.0,
  "precision": 0.0-10.0,
  "adaptability": 0.0-10.0,
  "meta_learning": 0.0-10.0,
  "consistency": 0.0-10.0,
  "self_awareness": 0.0-10.0,
  "overall": 0.0-10.0,
  "strengths": ["dimension that stands out"],
  "weaknesses": ["dimension that needs work"],
  "improvement_suggestion": "specific actionable suggestion"
}"""


@dataclass
class IntelligenceScore:
    score_id:       str
    session_id:     str
    task:           str
    response:       str
    agent_role:     str
    reasoning:      float
    knowledge:      float
    creativity:     float
    precision:      float
    adaptability:   float
    meta_learning:  float
    consistency:    float
    self_awareness: float
    overall:        float
    strengths:      List[str]
    weaknesses:     List[str]
    improvement:    str
    timestamp:      float


@dataclass
class IntelligenceProfile:
    period:         str
    scores_count:   int
    avg_overall:    float
    dimension_avgs: Dict[str, float]
    trend:          str        # improving | stable | declining
    top_strength:   str
    top_weakness:   str
    growth_rate:    float      # % change from prior period


class IntelligenceMonitor:
    def __init__(self, llm):
        self.llm = llm
        self._db  = None
        self._init_db()

    def _init_db(self):
        self._db = sqlite3.connect(str(INTEL_DB), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS scores (
            score_id TEXT PRIMARY KEY, session_id TEXT, task TEXT,
            response TEXT, agent_role TEXT,
            reasoning REAL, knowledge REAL, creativity REAL, precision REAL,
            adaptability REAL, meta_learning REAL, consistency REAL,
            self_awareness REAL, overall REAL,
            strengths TEXT, weaknesses TEXT, improvement TEXT,
            timestamp REAL)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS milestones (
            milestone_id TEXT PRIMARY KEY, name TEXT, description TEXT,
            dimension TEXT, threshold REAL, achieved_at REAL)""")
        self._db.commit()
        count = self._db.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        log.info(f"Intelligence Monitor: {count} evaluations recorded")

    # ── Evaluate a response ───────────────────────────────────────────────────
    async def evaluate(
        self,
        task: str,
        response: str,
        agent_role: str = "general",
        session_id: str = "default",
    ) -> IntelligenceScore:
        """Evaluate a response across all intelligence dimensions."""
        prompt = (
            f"Task: {task[:500]}\n\n"
            f"AI Response:\n{response[:1000]}\n\n"
            f"Evaluate this AI response:"
        )
        raw = await self.llm.complete(
            prompt, role="general",
            system=EVAL_SYSTEM, temperature=0.2
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
        except Exception:
            data = {d: 5.0 for d in DIMENSIONS}
            data["overall"] = 5.0
            data["strengths"] = []
            data["weaknesses"] = []
            data["improvement_suggestion"] = ""

        score = IntelligenceScore(
            score_id=uuid.uuid4().hex[:10],
            session_id=session_id,
            task=task[:200],
            response=response[:500],
            agent_role=agent_role,
            reasoning=float(data.get("reasoning", 5.0)),
            knowledge=float(data.get("knowledge", 5.0)),
            creativity=float(data.get("creativity", 5.0)),
            precision=float(data.get("precision", 5.0)),
            adaptability=float(data.get("adaptability", 5.0)),
            meta_learning=float(data.get("meta_learning", 5.0)),
            consistency=float(data.get("consistency", 5.0)),
            self_awareness=float(data.get("self_awareness", 5.0)),
            overall=float(data.get("overall", 5.0)),
            strengths=data.get("strengths", [])[:3],
            weaknesses=data.get("weaknesses", [])[:3],
            improvement=data.get("improvement_suggestion", ""),
            timestamp=time.time(),
        )

        self._save_score(score)
        self._check_milestones(score)
        return score

    # ── Get intelligence profile ──────────────────────────────────────────────
    def get_profile(self, period_days: int = 7) -> IntelligenceProfile:
        """Build intelligence profile for the last N days."""
        since = time.time() - period_days * 86400
        rows  = self._db.execute(
            "SELECT * FROM scores WHERE timestamp > ? ORDER BY timestamp",
            (since,)
        ).fetchall()

        if not rows:
            return IntelligenceProfile(
                period=f"last_{period_days}_days",
                scores_count=0,
                avg_overall=0.0,
                dimension_avgs={d: 0.0 for d in DIMENSIONS},
                trend="no_data",
                top_strength="",
                top_weakness="",
                growth_rate=0.0,
            )

        scores = [self._row_to_score(r) for r in rows]
        n = len(scores)

        # Average each dimension
        dim_avgs = {}
        for dim in DIMENSIONS:
            vals = [getattr(s, dim) for s in scores if hasattr(s, dim)]
            dim_avgs[dim] = round(sum(vals) / len(vals), 2) if vals else 0.0

        avg_overall = round(sum(s.overall for s in scores) / n, 2)

        # Trend: compare first half vs second half
        mid = n // 2
        first_half  = [s.overall for s in scores[:max(mid, 1)]]
        second_half = [s.overall for s in scores[max(mid, 1):]] or first_half
        first_avg  = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        diff = second_avg - first_avg
        if diff > 0.3:   trend = "improving"
        elif diff < -0.3: trend = "declining"
        else:             trend = "stable"

        growth_rate = round((second_avg - first_avg) / max(first_avg, 0.1) * 100, 1)

        top_strength = max(dim_avgs, key=dim_avgs.get)
        top_weakness = min(dim_avgs, key=dim_avgs.get)

        return IntelligenceProfile(
            period=f"last_{period_days}_days",
            scores_count=n,
            avg_overall=avg_overall,
            dimension_avgs=dim_avgs,
            trend=trend,
            top_strength=top_strength,
            top_weakness=top_weakness,
            growth_rate=growth_rate,
        )

    # ── Growth chart data ─────────────────────────────────────────────────────
    def growth_chart(self, days: int = 30, bucket_hours: int = 24) -> List[Dict]:
        """Returns time-series data for intelligence score chart."""
        since  = time.time() - days * 86400
        bucket = bucket_hours * 3600
        rows   = self._db.execute(
            "SELECT overall, timestamp FROM scores WHERE timestamp > ? ORDER BY timestamp",
            (since,)
        ).fetchall()

        if not rows:
            return []

        # Group into time buckets
        buckets: Dict[int, List[float]] = {}
        for overall, ts in rows:
            bucket_key = int(ts // bucket)
            buckets.setdefault(bucket_key, []).append(overall)

        return [
            {
                "timestamp": k * bucket,
                "avg_score": round(sum(v) / len(v), 2),
                "count":     len(v),
            }
            for k, v in sorted(buckets.items())
        ]

    # ── Dimension breakdown ───────────────────────────────────────────────────
    def dimension_breakdown(self) -> Dict[str, Dict]:
        """Current scores per dimension with trend."""
        result = {}
        for dim in DIMENSIONS:
            recent = self._db.execute(
                f"SELECT {dim} FROM scores ORDER BY timestamp DESC LIMIT 20"
            ).fetchall()
            if not recent:
                result[dim] = {"avg": 0.0, "trend": "no_data", "description": DIMENSIONS[dim]}
                continue
            vals   = [r[0] for r in recent]
            avg    = round(sum(vals) / len(vals), 2)
            first5 = sum(vals[-5:]) / min(5, len(vals))
            last5  = sum(vals[:5]) / min(5, len(vals))
            trend  = "up" if last5 - first5 > 0.2 else ("down" if first5 - last5 > 0.2 else "stable")
            result[dim] = {
                "avg": avg,
                "trend": trend,
                "description": DIMENSIONS[dim],
                "recent": vals[:5],
            }
        return result

    # ── Milestones ────────────────────────────────────────────────────────────
    def _check_milestones(self, score: IntelligenceScore):
        """Check if any intelligence milestones were achieved."""
        milestone_defs = [
            ("first_eval",       "First Evaluation",     "overall",  0.0),
            ("good_reasoning",   "Good Reasoner",         "reasoning", 7.0),
            ("expert_reasoning", "Expert Reasoner",       "reasoning", 9.0),
            ("precise",          "High Precision",        "precision", 8.0),
            ("creative",         "Creative Thinker",      "creativity", 8.0),
            ("self_aware",       "Self-Aware AI",         "self_awareness", 8.0),
            ("overall_7",        "Intelligence Level 7",  "overall",  7.0),
            ("overall_9",        "Intelligence Level 9",  "overall",  9.0),
        ]
        for mid, name, dim, threshold in milestone_defs:
            existing = self._db.execute(
                "SELECT 1 FROM milestones WHERE milestone_id=?", (mid,)
            ).fetchone()
            if not existing and getattr(score, dim, 0.0) >= threshold:
                self._db.execute(
                    "INSERT INTO milestones VALUES (?,?,?,?,?,?)",
                    (mid, name, f"Achieved {dim} >= {threshold}",
                     dim, threshold, time.time())
                )
                self._db.commit()
                log.info(f"🏆 Milestone achieved: {name}")

    def list_milestones(self) -> List[Dict]:
        rows = self._db.execute(
            "SELECT * FROM milestones ORDER BY achieved_at"
        ).fetchall()
        return [{"id": r[0], "name": r[1], "description": r[2],
                 "dimension": r[3], "threshold": r[4], "achieved_at": r[5]}
                for r in rows]

    # ── Overall stats ─────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        total = self._db.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        avg   = self._db.execute("SELECT AVG(overall) FROM scores").fetchone()[0] or 0
        milestones = self._db.execute("SELECT COUNT(*) FROM milestones").fetchone()[0]
        profile = self.get_profile(7)
        return {
            "total_evaluations": total,
            "avg_overall": round(avg, 2),
            "milestones_achieved": milestones,
            "7_day_trend": profile.trend,
            "7_day_growth": f"{profile.growth_rate:+.1f}%",
            "top_strength": profile.top_strength,
            "top_weakness": profile.top_weakness,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _save_score(self, s: IntelligenceScore):
        self._db.execute(
            "INSERT INTO scores VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s.score_id, s.session_id, s.task, s.response, s.agent_role,
             s.reasoning, s.knowledge, s.creativity, s.precision,
             s.adaptability, s.meta_learning, s.consistency, s.self_awareness,
             s.overall, json.dumps(s.strengths), json.dumps(s.weaknesses),
             s.improvement, s.timestamp)
        )
        self._db.commit()

    def _row_to_score(self, row) -> IntelligenceScore:
        return IntelligenceScore(
            score_id=row[0], session_id=row[1], task=row[2],
            response=row[3], agent_role=row[4],
            reasoning=row[5], knowledge=row[6], creativity=row[7],
            precision=row[8], adaptability=row[9], meta_learning=row[10],
            consistency=row[11], self_awareness=row[12], overall=row[13],
            strengths=json.loads(row[14] or "[]"),
            weaknesses=json.loads(row[15] or "[]"),
            improvement=row[16] or "", timestamp=row[17],
        )


import re
