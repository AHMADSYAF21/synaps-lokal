"""
Agent Orchestrator — Multi-Role AI Agents
Roles: Architect, Coder, Analyzer, Researcher
Supports tool execution, shared memory, streaming output.
"""

import json
import re
import logging
from typing import AsyncGenerator, Optional

from core.llm import LLMService
from core.memory import MemoryService
from core.tools import ToolRegistry

log = logging.getLogger("synapse.agents")


# ── System Prompts per Role ───────────────────────────────────────────────────
ROLE_PROMPTS = {
    "architect": """You are an expert SOFTWARE ARCHITECT.
Your job: design clear, scalable system architectures and break down complex tasks.
Always produce structured plans, component diagrams (text-based), and clear specs.
When given a coding task, define the structure BEFORE writing code.""",

    "coder": """You are an elite SOFTWARE ENGINEER.
Your job: write clean, efficient, production-ready code.
Always include error handling. Follow best practices.
When using tools, output EXACTLY in this JSON format inside <tool> tags:
<tool>{"name": "tool_name", "params": {...}}</tool>
After tool results, continue reasoning and coding.""",

    "analyzer": """You are a CODE ANALYST and DEBUGGER.
Your job: find bugs, performance issues, security flaws, and logical errors.
Always explain WHY something is wrong and provide a concrete fix.
Be systematic: list issues, then provide solutions.""",

    "researcher": """You are an expert RESEARCHER and INFORMATION SYNTHESIZER.
Your job: gather, analyze, and summarize information clearly.
Use web_fetch tool when you need real data.
Always cite your sources and highlight key findings.""",
}

# Router system prompt
ROUTER_PROMPT = """You are a task router for an AI system.
Given a user message, respond with ONLY ONE of these roles (no explanation):
- architect: for system design, planning, high-level architecture
- coder: for writing code, implementing features, fixing bugs
- analyzer: for debugging, code review, optimization, error analysis
- researcher: for finding information, explaining concepts, research

Respond with exactly one word (the role name)."""


class Agent:
    """Single-role agent with tool-use capability."""

    def __init__(
        self,
        role: str,
        llm: LLMService,
        tools: ToolRegistry,
        memory: MemoryService,
    ):
        self.role = role
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.system_prompt = ROLE_PROMPTS.get(role, "You are a helpful AI assistant.")
        self._pick_model = "coder" if role == "coder" else "general"

    async def run(self, task: str, context: str = "") -> str:
        full = ""
        async for chunk in self.run_stream(task, context):
            full += chunk
        return full

    async def run_stream(self, task: str, context: str = "") -> AsyncGenerator[str, None]:
        """Run agent with optional tool execution loop."""
        prompt = self._build_prompt(task, context)
        buffer = ""
        iteration = 0
        MAX_TOOL_LOOPS = 5

        while iteration < MAX_TOOL_LOOPS:
            iteration += 1
            async for token in self.llm.stream(prompt, role=self._pick_model, system=self.system_prompt):
                buffer += token
                yield token

                # Check if a tool call is complete in buffer
                if "<tool>" in buffer and "</tool>" in buffer:
                    tool_result = await self._extract_and_run_tool(buffer)
                    if tool_result:
                        # Yield tool status to frontend
                        yield f"\n\n**[Tool: {tool_result['tool']}]**\n"
                        if tool_result["result"].get("stdout"):
                            yield f"```\n{tool_result['result']['stdout'][:1000]}\n```\n\n"
                        # Continue reasoning with tool output
                        prompt = self._build_continuation_prompt(buffer, tool_result)
                        buffer = ""
                        break
            else:
                # No more tool calls → done
                break

    def _build_prompt(self, task: str, context: str) -> str:
        tool_list = self.tools.schema_str()
        parts = [
            f"Available tools:\n{tool_list}\n",
            f"To use a tool, write: <tool>{{\"name\": \"tool_name\", \"params\": {{...}}}}</tool>",
            "",
        ]
        if context:
            parts.append(f"[Relevant context from memory]\n{context}\n")
        parts.append(f"Task: {task}")
        return "\n".join(parts)

    def _build_continuation_prompt(self, previous: str, tool_result: dict) -> str:
        result_str = json.dumps(tool_result["result"], indent=2)
        return (
            f"{previous}\n\n"
            f"[Tool Result for {tool_result['tool']}]\n{result_str}\n\n"
            f"Continue your response based on this result:"
        )

    async def _extract_and_run_tool(self, text: str) -> Optional[dict]:
        """Parse <tool>...</tool> and execute it."""
        match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
        if not match:
            return None
        try:
            call = json.loads(match.group(1))
            tool_name = call.get("name", "")
            params = call.get("params", {})
            result = await self.tools.execute(tool_name, params)
            return {"tool": tool_name, "params": params, "result": result}
        except Exception as e:
            log.error(f"Tool parse error: {e}")
            return None


# ── Orchestrator ──────────────────────────────────────────────────────────────
class AgentOrchestrator:
    """Routes tasks to the right agent, with shared memory."""

    def __init__(self, llm: LLMService, memory: MemoryService, tools: ToolRegistry):
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.agents = {
            role: Agent(role, llm, tools, memory)
            for role in ROLE_PROMPTS.keys()
        }

    async def _route(self, task: str) -> str:
        """Determine which agent should handle this task."""
        result = await self.llm.complete(
            prompt=f"Task: {task}",
            role="general",
            system=ROUTER_PROMPT,
            temperature=0.1,
        )
        role = result.strip().lower().split()[0]
        if role not in self.agents:
            role = "coder"  # default fallback
        log.info(f"Routed to: {role}")
        return role

    async def run(self, task: str, session_id: str = "default", context: str = "") -> dict:
        role = await self._route(task)
        agent = self.agents[role]
        response = await agent.run(task, context)
        return {
            "role": role,
            "response": response,
            "session_id": session_id,
        }

    async def run_stream(
        self, task: str, session_id: str = "default", context: str = ""
    ) -> AsyncGenerator[str, None]:
        role = await self._route(task)
        agent = self.agents[role]

        # Emit agent role to frontend
        yield f"[AGENT:{role}]"

        async for chunk in agent.run_stream(task, context):
            yield chunk

    async def run_with_role(
        self, role: str, task: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """Force a specific agent role."""
        agent = self.agents.get(role, self.agents["coder"])
        async for chunk in agent.run_stream(task, context):
            yield chunk
