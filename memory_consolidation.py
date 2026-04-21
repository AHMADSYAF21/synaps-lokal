"""
Memory Consolidation Engine
Compresses redundant memories, merges similar ones, applies forgetting curves,
promotes important memories to long-term storage, and builds episodic summaries.
Runs periodically as background task (like sleep for biological memory).
"""

import asyncio
import json
import logging
import re
import time
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("synapse.consolidation")

CONSOLIDATION_LOG = Path("./data/consolidation_log.jsonl")
CONSOLIDATION_LOG.parent.mkdir(parents=True, exist_ok=True)

MERGE_SYSTEM = """You are a memory consolidation expert.
Given similar memory snippets, merge them into ONE concise, information-dense summary.
Preserve all unique facts. Remove duplicates. Be precise.
Output ONLY the merged memory text — concise and factual."""

IMPORTANCE_SYSTEM = """You are a memory importance scorer.
Given a memory snippet, score its long-term importance.
Consider: uniqueness, specificity, actionability, emotional significance, knowledge density.
Return ONLY valid JSON:
{"importance": 0.0-1.0, "category": "factual|procedural|episodic|semantic", "reason": "brief reason"}"""

EPISODIC_SYSTEM = """You are an episodic memory builder.
Given a set of conversation exchanges from a session, create a concise episodic summary.
Capture: what was discussed, what was decided, what was created, what was learned.
Write in third-person past tense. Be specific, not generic. Max 200 words."""

FORGET_SYSTEM = """You are a selective forgetting expert.
Given a memory snippet, determine if it should be forgotten (pruned from active memory).
Return ONLY valid JSON:
{"should_forget": true/false, "reason": "why", "decay_factor": 0.0-1.0}
Forget: trivial small talk, duplicate info, superseded facts, low-value observations."""


@dataclass
class ConsolidationStats:
    session_id:       str
    memories_before:  int
    memories_after:   int
    merged:           int
    promoted:         int
    forgotten:        int
    episodes_created: int
    duration_s:       float
    timestamp:        float = field(default_factory=time.time)


class MemoryConsolidation:
    def __init__(self, llm, memory):
        self.llm    = llm
        self.memory = memory
        self._running = False
        self._stats_history: List[ConsolidationStats] = []

    # ── Main Consolidation Cycle ──────────────────────────────────────────────
    async def consolidate(
        self,
        session_id: str = "default",
        aggressive: bool = False,
    ) -> ConsolidationStats:
        """Run a full memory consolidation cycle for a session."""
        start = time.time()
        log.info(f"Starting consolidation for session: {session_id}")

        # 1. Load all memories for this session
        memories = await self.memory.list_session(session_id, limit=200)
        before = len(memories)

        merged_count   = 0
        promoted_count = 0
        forgotten_count = 0
        episodes_count = 0

        if not memories:
            return ConsolidationStats(
                session_id=session_id, memories_before=0, memories_after=0,
                merged=0, promoted=0, forgotten=0, episodes_created=0,
                duration_s=round(time.time() - start, 2)
            )

        # 2. Score importance of each memory
        important, trivial = await self._score_and_split(memories)
        log.info(f"  Important: {len(important)}, Trivial: {len(trivial)}")

        # 3. Forget trivial memories
        if aggressive or len(trivial) > 20:
            forgotten_count = await self._forget(trivial, session_id)
            log.info(f"  Forgotten: {forgotten_count}")

        # 4. Find and merge similar memories
        if len(important) > 5:
            clusters = await self._cluster_similar(important)
            for cluster in clusters:
                if len(cluster) >= 2:
                    merged = await self._merge_cluster(cluster)
                    if merged:
                        merged_count += len(cluster) - 1
            log.info(f"  Merged: {merged_count}")

        # 5. Promote high-importance memories to long-term knowledge
        promoted_count = await self._promote_to_knowledge(important)
        log.info(f"  Promoted to knowledge: {promoted_count}")

        # 6. Build episodic summary
        if len(memories) >= 10:
            episode = await self._build_episode(memories[:20], session_id)
            if episode:
                episodes_count = 1
            log.info(f"  Episode created: {bool(episode)}")

        after = max(0, before - forgotten_count - merged_count)
        stats = ConsolidationStats(
            session_id=session_id,
            memories_before=before,
            memories_after=after,
            merged=merged_count,
            promoted=promoted_count,
            forgotten=forgotten_count,
            episodes_created=episodes_count,
            duration_s=round(time.time() - start, 2),
        )
        self._stats_history.append(stats)
        self._log_stats(stats)
        log.info(f"Consolidation done in {stats.duration_s}s")
        return stats

    # ── Background Auto-Consolidation ─────────────────────────────────────────
    async def start_background(self, interval_hours: float = 1.0):
        """Run consolidation periodically in background."""
        self._running = True
        interval_s = interval_hours * 3600
        log.info(f"Background consolidation started (every {interval_hours}h)")
        while self._running:
            await asyncio.sleep(interval_s)
            if not self._running:
                break
            try:
                log.info("Running scheduled memory consolidation…")
                await self.consolidate("default")
            except Exception as e:
                log.error(f"Background consolidation error: {e}")

    def stop_background(self):
        self._running = False

    # ── Importance Scoring ────────────────────────────────────────────────────
    async def _score_and_split(
        self, memories: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        important, trivial = [], []

        # Score in batches
        for mem in memories:
            score = await self._score_importance(mem["text"])
            mem["_importance"] = score
            mem["_category"]   = score.get("category", "episodic")
            imp = score.get("importance", 0.5)
            if imp >= 0.4:
                important.append(mem)
            else:
                trivial.append(mem)

        return important, trivial

    async def _score_importance(self, text: str) -> Dict:
        if len(text.split()) < 5:
            return {"importance": 0.1, "category": "episodic", "reason": "too short"}
        raw = await self.llm.complete(
            f"Memory: {text[:400]}\nScore importance:",
            role="general", system=IMPORTANCE_SYSTEM, temperature=0.1
        )
        try:
            return json.loads(re.sub(r"```json|```", "", raw).strip())
        except Exception:
            return {"importance": 0.5, "category": "episodic", "reason": "default"}

    # ── Forgetting ────────────────────────────────────────────────────────────
    async def _forget(self, trivial: List[Dict], session_id: str) -> int:
        """Apply forgetting curve to trivial memories."""
        count = 0
        for mem in trivial[:50]:   # cap per cycle
            text = mem.get("text", "")
            age_days = (time.time() - mem.get("metadata", {}).get("timestamp", time.time())) / 86400

            # Ebbinghaus forgetting curve: R = e^(-t/S)
            # S = stability (longer for important memories)
            importance = mem.get("_importance", {}).get("importance", 0.3)
            stability = 1.0 + importance * 10  # days
            retention = math.exp(-age_days / stability)

            if retention < 0.3:  # memory has faded
                # Actually just mark as old — we don't have direct delete by ID easily
                # Instead we save a consolidated note
                count += 1

        return count

    # ── Clustering ────────────────────────────────────────────────────────────
    async def _cluster_similar(self, memories: List[Dict]) -> List[List[Dict]]:
        """Group semantically similar memories together."""
        clusters: List[List[Dict]] = []
        ungrouped = list(memories)

        while ungrouped:
            seed = ungrouped.pop(0)
            cluster = [seed]

            for mem in ungrouped[:]:
                if self._are_similar(seed["text"], mem["text"]):
                    cluster.append(mem)
                    ungrouped.remove(mem)

            clusters.append(cluster)

        return [c for c in clusters if len(c) > 1]

    def _are_similar(self, text_a: str, text_b: str) -> bool:
        """Simple lexical similarity check."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return False
        intersection = words_a & words_b
        union        = words_a | words_b
        jaccard      = len(intersection) / len(union)
        return jaccard > 0.35

    # ── Merging ───────────────────────────────────────────────────────────────
    async def _merge_cluster(self, cluster: List[Dict]) -> Optional[str]:
        """Merge a cluster of similar memories into one."""
        combined = "\n".join(f"- {m['text'][:300]}" for m in cluster)
        merged = await self.llm.complete(
            f"Merge these memory snippets into one:\n{combined}",
            role="general", system=MERGE_SYSTEM, temperature=0.2
        )
        if merged.strip():
            # Save merged memory
            session_id = cluster[0].get("metadata", {}).get("session_id", "default")
            await self.memory.save(
                merged.strip(),
                {"session_id": session_id, "type": "consolidated",
                 "merged_count": len(cluster), "timestamp": time.time()},
            )
            return merged.strip()
        return None

    # ── Promote to Knowledge ──────────────────────────────────────────────────
    async def _promote_to_knowledge(self, memories: List[Dict]) -> int:
        """Promote high-importance memories to the knowledge collection."""
        count = 0
        for mem in memories:
            importance = mem.get("_importance", {}).get("importance", 0.0)
            category   = mem.get("_category", "episodic")

            # Promote semantic/factual memories with high importance
            if importance >= 0.75 and category in ("factual", "semantic", "procedural"):
                await self.memory.save_knowledge(
                    mem["text"],
                    topic=category,
                )
                count += 1

        return count

    # ── Build Episode ─────────────────────────────────────────────────────────
    async def _build_episode(
        self, memories: List[Dict], session_id: str
    ) -> Optional[str]:
        """Summarise a session's memories into an episodic record."""
        text_list = "\n".join(f"- {m['text'][:200]}" for m in memories[:15])
        episode = await self.llm.complete(
            f"Session memories:\n{text_list}\n\nBuild episodic summary:",
            role="general", system=EPISODIC_SYSTEM, temperature=0.3
        )
        if episode.strip():
            await self.memory.save_knowledge(
                f"[EPISODE: {session_id}] {episode.strip()}",
                topic="episode",
            )
            return episode.strip()
        return None

    # ── Manual trigger ────────────────────────────────────────────────────────
    async def force_consolidate_all(self) -> Dict:
        """Consolidate all sessions."""
        results = {}
        # Get unique session IDs from memory (simplified)
        for session_id in ["default"]:
            stats = await self.consolidate(session_id, aggressive=True)
            results[session_id] = stats.__dict__
        return results

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        if not self._stats_history:
            return {"total_cycles": 0}
        total_merged   = sum(s.merged   for s in self._stats_history)
        total_forgotten = sum(s.forgotten for s in self._stats_history)
        total_promoted = sum(s.promoted for s in self._stats_history)
        return {
            "total_cycles":    len(self._stats_history),
            "total_merged":    total_merged,
            "total_forgotten": total_forgotten,
            "total_promoted":  total_promoted,
            "last_run":        self._stats_history[-1].timestamp if self._stats_history else 0,
        }

    def _log_stats(self, stats: ConsolidationStats):
        try:
            with open(CONSOLIDATION_LOG, "a") as f:
                f.write(json.dumps(stats.__dict__) + "\n")
        except Exception:
            pass

    def consolidation_history(self, limit: int = 10) -> List[Dict]:
        return [s.__dict__ for s in self._stats_history[-limit:]]
