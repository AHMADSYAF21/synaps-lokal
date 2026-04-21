"""
Context Optimizer — Intelligent Context Window Management
Maximizes information density within LLM context limits.
Ranks relevance, compresses, deduplicates, and structures context
for optimal AI performance on each specific query.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("synapse.context")

# Characters per token (rough estimate)
CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 6000   # conservative for most models
HARD_MAX_TOKENS    = 12000  # for models with larger context

RELEVANCE_SYSTEM = """You are a context relevance scorer.
Given a query and a context snippet, score relevance.
Return ONLY valid JSON: {"relevance": 0.0-1.0, "reason": "brief"}"""

COMPRESS_SYSTEM = """You are an expert information compressor.
Compress the given text to half its length while preserving ALL key information.
Remove: filler words, redundant phrases, overly verbose explanations.
Keep: facts, numbers, names, actions, conclusions.
Output ONLY the compressed text."""

CONTEXT_BUILDER_SYSTEM = """You are a context architect.
Given a user query and multiple information sources,
build the optimal context to include in an LLM prompt.

Structure it as:
[CORE CONTEXT] - most relevant facts directly needed
[BACKGROUND] - supporting information
[CONSTRAINTS] - any limitations or requirements

Be concise. Every sentence must earn its place."""


@dataclass
class ContextChunk:
    text:      str
    source:    str      # memory | skill | document | knowledge
    relevance: float
    token_est: int
    timestamp: float = 0.0
    priority:  int = 5  # 1 (highest) to 10 (lowest)


@dataclass
class OptimizedContext:
    query:          str
    chunks:         List[ContextChunk]
    total_tokens:   int
    dropped_tokens: int
    compression_ratio: float
    build_time_ms:  float


class ContextOptimizer:
    def __init__(self, llm):
        self.llm = llm
        self._cache: Dict[str, OptimizedContext] = {}
        self._cache_ttl = 120  # seconds

    # ── Main: Build optimal context ───────────────────────────────────────────
    async def build(
        self,
        query: str,
        sources: Dict[str, List[str]],   # {"memory": [...], "skills": [...], ...}
        max_tokens: int = DEFAULT_MAX_TOKENS,
        structure: bool = True,
    ) -> str:
        """Build optimally ranked and compressed context for a query."""
        start = time.time()

        all_chunks: List[ContextChunk] = []

        # Convert sources to chunks
        for source_type, texts in sources.items():
            for text in texts:
                if not text or not text.strip():
                    continue
                tokens = len(text) // CHARS_PER_TOKEN
                all_chunks.append(ContextChunk(
                    text=text.strip(),
                    source=source_type,
                    relevance=0.5,   # default, will be scored
                    token_est=tokens,
                    timestamp=time.time(),
                ))

        if not all_chunks:
            return ""

        # Score relevance in parallel (batch for efficiency)
        scored = await self._score_relevance_batch(query, all_chunks)

        # Sort by relevance × priority
        scored.sort(key=lambda c: c.relevance * (1.0 / c.priority), reverse=True)

        # Fill context window greedily
        selected: List[ContextChunk] = []
        used_tokens = 0
        dropped_tokens = 0

        for chunk in scored:
            if used_tokens + chunk.token_est <= max_tokens:
                selected.append(chunk)
                used_tokens += chunk.token_est
            else:
                # Try to compress and fit
                if chunk.relevance > 0.7 and chunk.token_est > 50:
                    compressed = await self._compress(chunk.text)
                    new_tokens = len(compressed) // CHARS_PER_TOKEN
                    if used_tokens + new_tokens <= max_tokens:
                        chunk.text      = compressed
                        chunk.token_est = new_tokens
                        selected.append(chunk)
                        used_tokens += new_tokens
                    else:
                        dropped_tokens += chunk.token_est
                else:
                    dropped_tokens += chunk.token_est

        if not selected:
            return ""

        # Format context
        if structure:
            context = await self._structure_context(query, selected)
        else:
            context = self._format_flat(selected)

        total_input = sum(c.token_est for c in all_chunks)
        ratio = used_tokens / total_input if total_input > 0 else 1.0

        log.debug(
            f"Context built: {len(selected)}/{len(all_chunks)} chunks, "
            f"{used_tokens}/{total_input} tokens, ratio={ratio:.2f}"
        )
        return context

    # ── Batch relevance scoring ───────────────────────────────────────────────
    async def _score_relevance_batch(
        self, query: str, chunks: List[ContextChunk]
    ) -> List[ContextChunk]:
        """Score all chunks for relevance to query."""
        # For speed: use heuristic for most, LLM only for unclear ones
        query_words = set(query.lower().split())

        for chunk in chunks:
            chunk_words = set(chunk.text.lower().split())
            # Jaccard-based quick score
            if not chunk_words:
                chunk.relevance = 0.0
                continue
            overlap = len(query_words & chunk_words) / max(len(query_words | chunk_words), 1)
            # Boost based on source type
            source_boost = {"skill": 0.1, "knowledge": 0.15, "memory": 0.05}.get(chunk.source, 0)
            chunk.relevance = min(1.0, overlap * 3 + source_boost + 0.2)

        # For top chunks with unclear relevance, use LLM
        borderline = [c for c in chunks if 0.25 <= c.relevance <= 0.55][:5]
        for chunk in borderline:
            try:
                score = await self._llm_score_relevance(query, chunk.text)
                chunk.relevance = score
            except Exception:
                pass

        return chunks

    async def _llm_score_relevance(self, query: str, text: str) -> float:
        raw = await self.llm.complete(
            f"Query: {query}\nContext: {text[:300]}\nScore relevance:",
            role="general", system=RELEVANCE_SYSTEM, temperature=0.1
        )
        try:
            data = json.loads(re.sub(r"```json|```", "", raw).strip())
            return float(data.get("relevance", 0.5))
        except Exception:
            return 0.5

    # ── Compression ───────────────────────────────────────────────────────────
    async def _compress(self, text: str) -> str:
        if len(text) < 200:
            return text
        compressed = await self.llm.complete(
            f"Compress:\n{text}",
            role="general", system=COMPRESS_SYSTEM, temperature=0.2
        )
        return compressed.strip() if compressed.strip() else text

    # ── Structured formatting ─────────────────────────────────────────────────
    async def _structure_context(
        self, query: str, chunks: List[ContextChunk]
    ) -> str:
        # Group by source and relevance
        core       = [c for c in chunks if c.relevance >= 0.6]
        background = [c for c in chunks if 0.3 <= c.relevance < 0.6]
        context_parts = []

        if core:
            context_parts.append("[CORE CONTEXT]")
            for c in core[:4]:
                context_parts.append(f"[{c.source}] {c.text}")

        if background:
            context_parts.append("\n[BACKGROUND]")
            for c in background[:3]:
                context_parts.append(f"[{c.source}] {c.text[:200]}")

        return "\n".join(context_parts)

    def _format_flat(self, chunks: List[ContextChunk]) -> str:
        return "\n\n".join(
            f"[{c.source}] {c.text}" for c in chunks
        )

    # ── Analyse context quality ───────────────────────────────────────────────
    def analyse(self, context: str, query: str) -> Dict:
        """Analyse quality of a built context."""
        tokens     = len(context) // CHARS_PER_TOKEN
        words      = context.split()
        query_words = set(query.lower().split())
        ctx_words   = set(context.lower().split())
        coverage    = len(query_words & ctx_words) / max(len(query_words), 1)

        return {
            "token_count": tokens,
            "word_count":  len(words),
            "query_coverage": round(coverage, 3),
            "utilization": round(tokens / DEFAULT_MAX_TOKENS, 3),
            "has_structure": "[CORE CONTEXT]" in context,
        }

    # ── Sliding window for long conversations ─────────────────────────────────
    def sliding_window(
        self,
        messages: List[Dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> List[Dict]:
        """Keep only the most recent messages that fit in the context window."""
        result = []
        used   = 0

        # Always include system message
        system_msgs = [m for m in messages if m.get("role") == "system"]
        for m in system_msgs:
            tokens = len(str(m.get("content", ""))) // CHARS_PER_TOKEN
            used  += tokens
            result.append(m)

        # Add recent messages (newest first, then reverse)
        regular = [m for m in messages if m.get("role") != "system"]
        selected_regular = []

        for msg in reversed(regular):
            tokens = len(str(msg.get("content", ""))) // CHARS_PER_TOKEN
            if used + tokens <= max_tokens:
                selected_regular.insert(0, msg)
                used += tokens
            else:
                break

        return result + selected_regular

    # ── Smart truncation ─────────────────────────────────────────────────────
    def smart_truncate(
        self,
        text: str,
        max_tokens: int,
        keep_start_ratio: float = 0.3,
    ) -> str:
        """Truncate text intelligently — keep beginning and end."""
        max_chars = max_tokens * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text

        keep_start = int(max_chars * keep_start_ratio)
        keep_end   = max_chars - keep_start - 20

        start = text[:keep_start]
        end   = text[-keep_end:] if keep_end > 0 else ""
        mid   = f"\n[... {len(text) - keep_start - keep_end} chars omitted ...]\n"

        return start + mid + end

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        return {"cached_contexts": len(self._cache)}
