"""
Multi-Agent Collaboration System
Agents work together: debate, critique, peer-review, brainstorm, vote.
Modes: debate | council | pipeline | peer_review | brainstorm
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional

log = logging.getLogger("synapse.collab")

# ── Role Definitions ──────────────────────────────────────────────────────────
COLLAB_ROLES = {
    "optimist": {
        "system": "You are an optimistic creative thinker. Focus on possibilities, strengths, and innovative ideas. Be enthusiastic but grounded.",
        "icon": "🌟",
    },
    "critic": {
        "system": "You are a rigorous critical analyst. Find flaws, risks, edge cases, and weaknesses. Be constructive but thorough.",
        "icon": "🔍",
    },
    "pragmatist": {
        "system": "You are a practical implementer. Focus on feasibility, resources, timelines, and real-world constraints.",
        "icon": "🔧",
    },
    "architect": {
        "system": "You are a systems architect. Think about structure, scalability, maintainability, and long-term design.",
        "icon": "📐",
    },
    "ethicist": {
        "system": "You are an ethics and security specialist. Identify risks, biases, unintended consequences, and ethical concerns.",
        "icon": "⚖️",
    },
    "researcher": {
        "system": "You are a deep researcher. Provide context, background, relevant examples, and reference points from knowledge.",
        "icon": "📚",
    },
}

MODERATOR_SYSTEM = """You are a debate moderator and synthesiser.
Given multiple expert perspectives on a topic, synthesise them into:
1. Key points of agreement
2. Key tensions or disagreements  
3. Best combined recommendation
4. Confidence level (0-10)

Be concise and structured. Return as JSON:
{"agreements": [...], "tensions": [...], "recommendation": "...", "confidence": N}"""

VOTE_SYSTEM = """You are a neutral judge evaluating multiple solutions.
Score each solution 0-10 on: correctness, completeness, clarity, feasibility.
Return ONLY valid JSON array:
[{"id": 1, "scores": {"correctness":N,"completeness":N,"clarity":N,"feasibility":N}, "overall": N, "verdict": "..."}]"""


@dataclass
class AgentMessage:
    agent_id:   str
    role:       str
    icon:       str
    content:    str
    timestamp:  float
    round_num:  int


@dataclass
class CollabSession:
    session_id: str
    mode:       str
    topic:      str
    agents:     List[str]
    messages:   List[AgentMessage] = field(default_factory=list)
    synthesis:  str = ""
    winner:     str = ""
    started_at: float = 0.0
    finished_at: float = 0.0


class MultiAgentCollaboration:
    def __init__(self, llm):
        self.llm = llm

    # ── Main Entry ────────────────────────────────────────────────────────────
    async def run(
        self,
        topic: str,
        mode: str = "council",
        agents: Optional[List[str]] = None,
        rounds: int = 2,
    ) -> CollabSession:
        """Run a full multi-agent collaboration session."""
        session_id = f"collab-{int(time.time())}"
        agent_ids  = agents or self._default_agents(mode)
        session    = CollabSession(
            session_id=session_id, mode=mode, topic=topic,
            agents=agent_ids, started_at=time.time()
        )

        if mode == "debate":
            await self._debate(session, rounds)
        elif mode == "council":
            await self._council(session)
        elif mode == "pipeline":
            await self._pipeline(session)
        elif mode == "peer_review":
            await self._peer_review(session)
        elif mode == "brainstorm":
            await self._brainstorm(session)
        else:
            await self._council(session)

        session.finished_at = time.time()
        return session

    async def run_stream(
        self,
        topic: str,
        mode: str = "council",
        agents: Optional[List[str]] = None,
        rounds: int = 2,
    ) -> AsyncGenerator[str, None]:
        """Stream collaboration in real-time."""
        agent_ids = agents or self._default_agents(mode)

        yield f"[COLLAB_START] mode={mode} agents={','.join(agent_ids)}\n\n"

        if mode == "debate":
            async for chunk in self._debate_stream(topic, agent_ids, rounds):
                yield chunk
        elif mode == "council":
            async for chunk in self._council_stream(topic, agent_ids):
                yield chunk
        elif mode == "pipeline":
            async for chunk in self._pipeline_stream(topic, agent_ids):
                yield chunk
        elif mode == "peer_review":
            async for chunk in self._peer_review_stream(topic, agent_ids):
                yield chunk
        elif mode == "brainstorm":
            async for chunk in self._brainstorm_stream(topic, agent_ids):
                yield chunk
        else:
            async for chunk in self._council_stream(topic, agent_ids):
                yield chunk

    # ── Mode: Council — each agent gives perspective, then synthesise ─────────
    async def _council_stream(
        self, topic: str, agent_ids: List[str]
    ) -> AsyncGenerator[str, None]:
        responses = {}
        for agent_id in agent_ids:
            role_info = COLLAB_ROLES.get(agent_id, COLLAB_ROLES["researcher"])
            yield f"\n**{role_info['icon']} {agent_id.upper()}**\n"

            prompt  = f"Topic: {topic}\n\nProvide your expert perspective:"
            content = ""
            async for token in self.llm.stream(
                prompt, role="general", system=role_info["system"]
            ):
                content += token
                yield token

            responses[agent_id] = content
            yield "\n\n"

        # Synthesise
        yield "---\n**🎯 SYNTHESIS**\n"
        context = "\n\n".join(
            f"{aid.upper()}: {resp[:600]}" for aid, resp in responses.items()
        )
        prompt = f"Topic: {topic}\n\nExpert perspectives:\n{context}"
        async for token in self.llm.stream(prompt, role="general",
                                            system=MODERATOR_SYSTEM):
            yield token

    async def _council(self, session: CollabSession):
        full = ""
        async for chunk in self._council_stream(session.topic, session.agents):
            full += chunk
        session.synthesis = full

    # ── Mode: Debate — two agents argue, judge decides ────────────────────────
    async def _debate_stream(
        self, topic: str, agent_ids: List[str], rounds: int
    ) -> AsyncGenerator[str, None]:
        if len(agent_ids) < 2:
            agent_ids = ["optimist", "critic"]
        a1, a2 = agent_ids[0], agent_ids[1]
        r1_info = COLLAB_ROLES.get(a1, COLLAB_ROLES["optimist"])
        r2_info = COLLAB_ROLES.get(a2, COLLAB_ROLES["critic"])

        history = f"Debate topic: {topic}\n\n"
        for rnd in range(1, rounds + 1):
            yield f"**Round {rnd}**\n\n"

            # Agent 1
            yield f"{r1_info['icon']} **{a1.upper()}:**\n"
            a1_resp = ""
            prompt1 = f"{history}\nPresent your argument (Round {rnd}):"
            async for tok in self.llm.stream(
                prompt1, role="general", system=r1_info["system"]
            ):
                a1_resp += tok; yield tok
            history += f"\n{a1.upper()}: {a1_resp[:400]}\n"
            yield "\n\n"

            # Agent 2 responds
            yield f"{r2_info['icon']} **{a2.upper()}:**\n"
            a2_resp = ""
            prompt2 = f"{history}\nCounter-argue or respond (Round {rnd}):"
            async for tok in self.llm.stream(
                prompt2, role="general", system=r2_info["system"]
            ):
                a2_resp += tok; yield tok
            history += f"\n{a2.upper()}: {a2_resp[:400]}\n"
            yield "\n\n"

        # Judge
        yield "---\n**⚖️ VERDICT**\n"
        judge_prompt = (
            f"Debate topic: {topic}\n\nFull debate:\n{history}\n\n"
            f"Who made the stronger argument and why?"
        )
        async for tok in self.llm.stream(judge_prompt, role="general"):
            yield tok

    async def _debate(self, session: CollabSession, rounds: int):
        full = ""
        async for chunk in self._debate_stream(session.topic, session.agents, rounds):
            full += chunk
        session.synthesis = full

    # ── Mode: Pipeline — each agent builds on the previous ───────────────────
    async def _pipeline_stream(
        self, topic: str, agent_ids: List[str]
    ) -> AsyncGenerator[str, None]:
        current = f"Initial task: {topic}"

        for i, agent_id in enumerate(agent_ids):
            role_info = COLLAB_ROLES.get(agent_id, COLLAB_ROLES["researcher"])
            step = i + 1
            yield f"**Step {step}: {role_info['icon']} {agent_id.upper()}**\n"

            prompt  = f"{current}\n\nContribute your expertise to improve this:"
            content = ""
            async for tok in self.llm.stream(
                prompt, role="general", system=role_info["system"]
            ):
                content += tok; yield tok

            current = f"Previous work:\n{content[:800]}\n\nContinue:"
            yield "\n\n"

        yield "---\n**✅ FINAL RESULT**\n"
        yield content

    async def _pipeline(self, session: CollabSession):
        full = ""
        async for chunk in self._pipeline_stream(session.topic, session.agents):
            full += chunk
        session.synthesis = full

    # ── Mode: Peer Review ─────────────────────────────────────────────────────
    async def _peer_review_stream(
        self, topic: str, agent_ids: List[str]
    ) -> AsyncGenerator[str, None]:
        # Step 1: First agent produces work
        author  = agent_ids[0] if agent_ids else "architect"
        reviewers = agent_ids[1:] or ["critic", "pragmatist"]

        author_info = COLLAB_ROLES.get(author, COLLAB_ROLES["architect"])
        yield f"**{author_info['icon']} {author.upper()} — Draft**\n"

        draft = ""
        async for tok in self.llm.stream(
            f"Create a solution for: {topic}",
            role="general", system=author_info["system"]
        ):
            draft += tok; yield tok
        yield "\n\n---\n"

        # Step 2: Reviewers critique
        all_reviews = []
        for reviewer_id in reviewers[:3]:
            rev_info = COLLAB_ROLES.get(reviewer_id, COLLAB_ROLES["critic"])
            yield f"**{rev_info['icon']} {reviewer_id.upper()} — Review**\n"
            review = ""
            prompt = (f"Review this solution:\n\n{draft[:800]}\n\n"
                      f"Provide specific, actionable feedback:")
            async for tok in self.llm.stream(
                prompt, role="general", system=rev_info["system"]
            ):
                review += tok; yield tok
            all_reviews.append(f"{reviewer_id}: {review[:400]}")
            yield "\n\n"

        # Step 3: Author revises
        yield f"**{author_info['icon']} {author.upper()} — Revised**\n"
        reviews_text = "\n".join(all_reviews)
        async for tok in self.llm.stream(
            f"Original: {draft[:600]}\n\nReviews: {reviews_text}\n\nRevise incorporating feedback:",
            role="general", system=author_info["system"]
        ):
            yield tok

    async def _peer_review(self, session: CollabSession):
        full = ""
        async for chunk in self._peer_review_stream(session.topic, session.agents):
            full += chunk
        session.synthesis = full

    # ── Mode: Brainstorm ──────────────────────────────────────────────────────
    async def _brainstorm_stream(
        self, topic: str, agent_ids: List[str]
    ) -> AsyncGenerator[str, None]:
        all_ideas = []
        yield f"**💡 BRAINSTORM: {topic}**\n\n"

        # Each agent contributes ideas
        for agent_id in agent_ids:
            role_info = COLLAB_ROLES.get(agent_id, COLLAB_ROLES["researcher"])
            yield f"{role_info['icon']} **{agent_id.upper()}** ideas:\n"
            ideas = ""
            async for tok in self.llm.stream(
                f"Topic: {topic}\nGenerate 3 creative, distinct ideas (numbered list):",
                role="general", system=role_info["system"]
            ):
                ideas += tok; yield tok
            all_ideas.append(ideas)
            yield "\n\n"

        # Select & combine best ideas
        yield "---\n**🏆 TOP IDEAS (Synthesis)**\n"
        combined = "\n\n".join(all_ideas[:4])
        async for tok in self.llm.stream(
            f"Topic: {topic}\n\nAll ideas:\n{combined}\n\n"
            f"Select the 3 best ideas and explain why they're promising:",
            role="general"
        ):
            yield tok

    async def _brainstorm(self, session: CollabSession):
        full = ""
        async for chunk in self._brainstorm_stream(session.topic, session.agents):
            full += chunk
        session.synthesis = full

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _default_agents(self, mode: str) -> List[str]:
        defaults = {
            "debate":      ["optimist", "critic"],
            "council":     ["optimist", "critic", "pragmatist"],
            "pipeline":    ["researcher", "architect", "pragmatist", "critic"],
            "peer_review": ["architect", "critic", "pragmatist"],
            "brainstorm":  ["optimist", "researcher", "pragmatist"],
        }
        return defaults.get(mode, ["optimist", "critic", "pragmatist"])

    def list_roles(self) -> Dict:
        return {k: {"icon": v["icon"], "description": v["system"][:80] + "…"}
                for k, v in COLLAB_ROLES.items()}

    def list_modes(self) -> Dict:
        return {
            "debate":      "Two agents argue opposing sides, judge decides",
            "council":     "Each agent gives their expert perspective, then synthesise",
            "pipeline":    "Agents build sequentially on each other's work",
            "peer_review": "One agent drafts, others review, author revises",
            "brainstorm":  "All agents generate ideas, best ones selected",
        }
