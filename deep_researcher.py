"""
Deep Researcher — Autonomous Multi-Query Research Engine
Plans research → runs parallel searches → reads full articles
→ cross-references → synthesises → produces structured report
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional

log = logging.getLogger("synapse.researcher")

PLANNER_SYSTEM = """You are a research planning expert.
Given a research topic, generate a comprehensive research plan.
Return ONLY valid JSON:
{
  "title": "Research title",
  "objective": "What we want to find out",
  "queries": ["specific search query 1", "query 2", "query 3", "query 4", "query 5"],
  "subtopics": ["subtopic 1", "subtopic 2", "subtopic 3"],
  "expected_sections": ["Introduction", "Section 1", ...]
}"""

EXTRACTOR_SYSTEM = """You are a research content extractor.
Given a webpage or article text, extract:
- Key facts and statistics
- Important quotes (brief)
- Main arguments or findings
- Source credibility signals
Return as structured bullet points. Be concise."""

SYNTHESISER_SYSTEM = """You are an expert research synthesiser.
Given research findings from multiple sources, write a comprehensive, structured report.
Include: executive summary, main findings, supporting evidence, contradictions found,
conclusions, and confidence level (0-10).
Use clear sections with headers. Cite sources as [1], [2], etc."""

CRITIC_SYSTEM = """You are a research quality critic.
Evaluate the research completeness and reliability.
Identify: gaps, potential biases, unverified claims, areas needing more research.
Return JSON: {"score": 0-10, "gaps": [...], "biases": [...], "recommendations": [...]}"""


@dataclass
class ResearchQuery:
    query:    str
    results:  List[Dict] = field(default_factory=list)
    summary:  str = ""
    error:    str = ""


@dataclass
class ResearchReport:
    topic:     str
    title:     str
    objective: str
    queries:   List[str]
    subtopics: List[str]
    sections:  Dict[str, str] = field(default_factory=dict)
    citations: List[Dict]     = field(default_factory=list)
    summary:   str = ""
    critique:  Dict           = field(default_factory=dict)
    confidence: float         = 0.0
    duration_s: float         = 0.0
    word_count: int           = 0


class DeepResearcher:
    def __init__(self, llm, web_search, memory):
        self.llm        = llm
        self.web_search = web_search
        self.memory     = memory

    # ── Main Research Entry ───────────────────────────────────────────────────
    async def research(
        self,
        topic: str,
        depth: str = "standard",   # quick | standard | deep
        use_memory: bool = True,
    ) -> ResearchReport:
        """Full automated research pipeline."""
        start = time.time()
        log.info(f"Research: '{topic}' depth={depth}")

        # 1. Plan research
        plan = await self._plan(topic)
        n_queries = {"quick": 2, "standard": 4, "deep": 6}.get(depth, 4)
        queries   = plan.get("queries", [topic])[:n_queries]
        subtopics = plan.get("subtopics", [])

        report = ResearchReport(
            topic     = topic,
            title     = plan.get("title", topic),
            objective = plan.get("objective", ""),
            queries   = queries,
            subtopics = subtopics,
        )

        # 2. Execute searches in parallel
        search_tasks = [self._search_and_extract(q) for q in queries]
        query_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # 3. Collect all findings
        all_findings = []
        citations    = []
        for i, result in enumerate(query_results):
            if isinstance(result, Exception):
                log.warning(f"Query {i} failed: {result}")
                continue
            qr = result
            all_findings.append(f"Query: {qr.query}\nFindings: {qr.summary}")
            for r in qr.results:
                if r.get("url") and r.get("url") not in [c["url"] for c in citations]:
                    citations.append({
                        "index": len(citations) + 1,
                        "title": r.get("title", "")[:80],
                        "url":   r.get("url", ""),
                        "snippet": r.get("snippet", "")[:150],
                    })

        report.citations = citations

        # 4. Check memory for related prior research
        memory_context = ""
        if use_memory:
            memories = await self.memory.search(topic, n=3, collection="knowledge")
            if memories:
                memory_context = "\n[Prior Research Context]\n" + "\n".join(
                    m["text"][:200] for m in memories
                )

        # 5. Synthesise into report sections
        combined = "\n\n---\n\n".join(all_findings)
        sections = await self._synthesise(
            topic, combined + memory_context, plan.get("expected_sections", [])
        )
        report.sections = sections

        # 6. Critique
        all_text = "\n".join(sections.values())
        report.critique = await self._critique(topic, all_text)
        report.confidence = report.critique.get("score", 5.0)

        # 7. Executive summary
        report.summary = sections.get("Executive Summary", "") or sections.get(
            list(sections.keys())[0] if sections else "", ""
        )[:500]

        # 8. Save to memory
        await self.memory.save_knowledge(
            f"Research on '{topic}': {report.summary}",
            topic=topic
        )

        report.duration_s  = round(time.time() - start, 1)
        report.word_count  = sum(len(s.split()) for s in sections.values())

        return report

    async def research_stream(
        self,
        topic: str,
        depth: str = "standard",
    ) -> AsyncGenerator[str, None]:
        """Stream research progress in real-time."""
        start = time.time()
        yield f"[RESEARCH] Planning research on: **{topic}**\n\n"

        # Plan
        plan     = await self._plan(topic)
        n_q      = {"quick": 2, "standard": 4, "deep": 6}.get(depth, 4)
        queries  = plan.get("queries", [topic])[:n_q]

        yield f"**Research Plan:**\n"
        yield f"- Title: {plan.get('title', topic)}\n"
        yield f"- Queries: {len(queries)}\n"
        yield f"- Subtopics: {', '.join(plan.get('subtopics', [])[:3])}\n\n"

        # Search
        all_findings = []
        citations    = []
        for i, q in enumerate(queries, 1):
            yield f"**[{i}/{len(queries)}] Searching:** _{q}_\n"
            qr = await self._search_and_extract(q)
            if qr.error:
                yield f"  ⚠️ {qr.error}\n\n"
            else:
                yield f"  ✅ {len(qr.results)} results found\n"
                if qr.summary:
                    yield f"  → {qr.summary[:150]}…\n\n"
                all_findings.append(f"Query: {q}\nFindings: {qr.summary}")
                for r in qr.results:
                    if r.get("url") and r.get("url") not in [c["url"] for c in citations]:
                        citations.append({
                            "index": len(citations)+1,
                            "title": r.get("title","")[:60],
                            "url":   r.get("url",""),
                        })

        yield f"\n**Synthesising {len(all_findings)} findings…**\n\n"

        # Synthesise streaming
        combined = "\n\n---\n\n".join(all_findings)
        sections = plan.get("expected_sections", ["Summary", "Findings", "Conclusions"])
        prompt   = (
            f"Research topic: {topic}\n\nFindings:\n{combined[:6000]}\n\n"
            f"Write a comprehensive research report with sections: {', '.join(sections)}."
        )
        async for token in self.llm.stream(prompt, role="general", system=SYNTHESISER_SYSTEM):
            yield token

        # Citations
        if citations:
            yield f"\n\n---\n**Sources:**\n"
            for c in citations[:10]:
                yield f"[{c['index']}] {c['title']} — {c['url']}\n"

        yield f"\n\n*Research completed in {round(time.time()-start, 1)}s*\n"

    # ── Plan ──────────────────────────────────────────────────────────────────
    async def _plan(self, topic: str) -> Dict:
        raw = await self.llm.complete(
            f"Create a research plan for: {topic}",
            role="general", system=PLANNER_SYSTEM, temperature=0.3
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {
                "title":     topic,
                "objective": f"Research {topic} comprehensively",
                "queries":   [topic, f"{topic} overview", f"{topic} examples", f"latest {topic}"],
                "subtopics": [],
                "expected_sections": ["Summary", "Key Findings", "Analysis", "Conclusions"],
            }

    # ── Search + Extract ──────────────────────────────────────────────────────
    async def _search_and_extract(self, query: str) -> ResearchQuery:
        qr = ResearchQuery(query=query)
        try:
            search_result = await self.web_search.search(query, n=6, summarise=False)
            qr.results    = search_result.get("results", [])

            # Extract key info from snippets
            snippets = "\n".join(
                f"[{i+1}] {r['title']}: {r['snippet']}"
                for i, r in enumerate(qr.results[:5])
            )
            summary = await self.llm.complete(
                f"Query: {query}\n\nSearch results:\n{snippets}\n\nExtract key facts:",
                role="general", system=EXTRACTOR_SYSTEM, temperature=0.2
            )
            qr.summary = summary

        except Exception as e:
            qr.error = str(e)

        return qr

    # ── Synthesise ────────────────────────────────────────────────────────────
    async def _synthesise(
        self, topic: str, combined: str, section_names: List[str]
    ) -> Dict[str, str]:
        sections_str = ", ".join(section_names) if section_names else "Key Findings, Analysis, Conclusions"
        prompt = (
            f"Research topic: {topic}\n\n"
            f"Research findings:\n{combined[:6000]}\n\n"
            f"Write a comprehensive research report. Include these sections: {sections_str}.\n"
            f"Use ## for section headers."
        )
        raw = await self.llm.complete(prompt, role="general", system=SYNTHESISER_SYSTEM)

        # Parse into sections
        sections: Dict[str, str] = {}
        current_section = "Overview"
        current_content: List[str] = []

        for line in raw.splitlines():
            if line.startswith("## "):
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section  = line[3:].strip()
                current_content  = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections if sections else {"Full Report": raw}

    # ── Critique ──────────────────────────────────────────────────────────────
    async def _critique(self, topic: str, report_text: str) -> Dict:
        raw = await self.llm.complete(
            f"Topic: {topic}\n\nReport:\n{report_text[:3000]}\n\nEvaluate quality:",
            role="general", system=CRITIC_SYSTEM, temperature=0.2
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {"score": 6.0, "gaps": [], "biases": [], "recommendations": []}

    # ── Format as Markdown ────────────────────────────────────────────────────
    def format_report(self, report: ResearchReport) -> str:
        parts = [
            f"# {report.title}\n",
            f"*Research on: {report.topic}*\n",
            f"*Queries run: {len(report.queries)} | Sources: {len(report.citations)} | Words: {report.word_count} | Confidence: {report.confidence}/10*\n",
            f"*Duration: {report.duration_s}s*\n\n---\n",
        ]
        for section, content in report.sections.items():
            parts.append(f"## {section}\n\n{content}\n")

        if report.citations:
            parts.append("\n## Sources\n")
            for c in report.citations:
                parts.append(f"[{c['index']}] [{c['title']}]({c['url']})")

        if report.critique.get("gaps"):
            parts.append(f"\n## Research Gaps\n")
            for gap in report.critique["gaps"][:3]:
                parts.append(f"- {gap}")

        return "\n".join(parts)
