"""
Tool Registry — Agent Tools
code_executor, file_manager, terminal_executor, web_fetch
"""

import asyncio
import subprocess
import tempfile
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("synapse.tools")

WORKSPACE = Path("./workspace")
WORKSPACE.mkdir(exist_ok=True)

MAX_OUTPUT_LEN = 8000


# ── Base Tool ─────────────────────────────────────────────────────────────────
class Tool:
    name: str = ""
    description: str = ""
    parameters: dict = {}

    async def run(self, params: dict) -> dict:
        raise NotImplementedError

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ── Tool 1: Code Executor ─────────────────────────────────────────────────────
class CodeExecutor(Tool):
    name = "code_executor"
    description = "Execute Python or JavaScript code and return output"
    parameters = {
        "code": "string — the code to run",
        "language": "string — 'python' or 'javascript'",
        "timeout": "int (optional) — max seconds, default 15",
    }

    async def run(self, params: dict) -> dict:
        code = params.get("code", "")
        lang = params.get("language", "python").lower()
        timeout = min(int(params.get("timeout", 15)), 30)

        if not code.strip():
            return {"success": False, "error": "No code provided"}

        try:
            if lang == "python":
                return await self._run_python(code, timeout)
            elif lang in ("javascript", "js", "node"):
                return await self._run_node(code, timeout)
            else:
                return {"success": False, "error": f"Unsupported language: {lang}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _run_python(self, code: str, timeout: int) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode()[:MAX_OUTPUT_LEN],
                "stderr": stderr.decode()[:MAX_OUTPUT_LEN],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "error": f"Timeout after {timeout}s"}
        finally:
            os.unlink(path)

    async def _run_node(self, code: str, timeout: int) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode()[:MAX_OUTPUT_LEN],
                "stderr": stderr.decode()[:MAX_OUTPUT_LEN],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "error": f"Timeout after {timeout}s"}
        finally:
            os.unlink(path)


# ── Tool 2: File Manager ──────────────────────────────────────────────────────
class FileManager(Tool):
    name = "file_manager"
    description = "Read, write, list, and delete files in the workspace"
    parameters = {
        "action": "string — 'read' | 'write' | 'list' | 'delete' | 'exists'",
        "path": "string — relative path inside workspace",
        "content": "string (optional) — content to write",
    }

    def _safe_path(self, rel_path: str) -> Path:
        """Prevent path traversal outside workspace."""
        target = (WORKSPACE / rel_path).resolve()
        if not str(target).startswith(str(WORKSPACE.resolve())):
            raise PermissionError(f"Access denied: {rel_path}")
        return target

    async def run(self, params: dict) -> dict:
        action = params.get("action", "read")
        rel = params.get("path", "")
        content = params.get("content", "")

        try:
            if action == "list":
                target = self._safe_path(rel or ".")
                if target.is_dir():
                    entries = [
                        {"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else 0}
                        for p in sorted(target.iterdir())
                    ]
                    return {"success": True, "entries": entries}
                return {"success": False, "error": "Not a directory"}

            elif action == "read":
                target = self._safe_path(rel)
                if not target.exists():
                    return {"success": False, "error": "File not found"}
                text = target.read_text(errors="replace")
                return {"success": True, "content": text[:MAX_OUTPUT_LEN], "size": len(text)}

            elif action == "write":
                target = self._safe_path(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                return {"success": True, "path": str(target.relative_to(WORKSPACE)), "bytes": len(content)}

            elif action == "delete":
                target = self._safe_path(rel)
                if target.is_file():
                    target.unlink()
                    return {"success": True}
                return {"success": False, "error": "Not a file"}

            elif action == "exists":
                target = self._safe_path(rel)
                return {"success": True, "exists": target.exists()}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except PermissionError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Tool 3: Terminal Executor ─────────────────────────────────────────────────
class TerminalExecutor(Tool):
    name = "terminal_executor"
    description = "Run shell commands in the workspace (safe subset)"
    parameters = {
        "command": "string — shell command to run",
        "timeout": "int (optional) — max seconds, default 20",
    }

    # Commands that are explicitly BLOCKED for safety
    BLOCKED = {"rm -rf /", ":(){ :|:& };:", "mkfs", "dd if=", "shutdown", "reboot", "passwd"}

    async def run(self, params: dict) -> dict:
        command = params.get("command", "").strip()
        timeout = min(int(params.get("timeout", 20)), 60)

        if not command:
            return {"success": False, "error": "No command"}

        for blocked in self.BLOCKED:
            if blocked in command:
                return {"success": False, "error": f"Blocked command: {blocked}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode()[:MAX_OUTPUT_LEN],
                "stderr": stderr.decode()[:MAX_OUTPUT_LEN],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Timeout after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Tool 4: Web Fetch ─────────────────────────────────────────────────────────
class WebFetch(Tool):
    name = "web_fetch"
    description = "Fetch content from a URL (text/HTML only)"
    parameters = {
        "url": "string — URL to fetch",
        "max_chars": "int (optional) — max characters to return, default 5000",
    }

    async def run(self, params: dict) -> dict:
        url = params.get("url", "").strip()
        max_chars = int(params.get("max_chars", 5000))

        if not url:
            return {"success": False, "error": "No URL"}
        if not url.startswith(("http://", "https://")):
            return {"success": False, "error": "Invalid URL scheme"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "SynapseBot/1.0"})
                content_type = resp.headers.get("content-type", "")
                if "text" not in content_type and "json" not in content_type:
                    return {"success": False, "error": f"Non-text content: {content_type}"}
                text = resp.text[:max_chars]
                return {
                    "success": True,
                    "url": url,
                    "status": resp.status_code,
                    "content": text,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Registry ──────────────────────────────────────────────────────────────────
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register(CodeExecutor())
        self._register(FileManager())
        self._register(TerminalExecutor())
        self._register(WebFetch())
        log.info(f"Tools registered: {list(self._tools.keys())}")

    def _register(self, tool: Tool):
        self._tools[tool.name] = tool

    async def execute(self, tool_name: str, params: dict) -> dict:
        if tool_name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        log.info(f"Executing tool: {tool_name} params={list(params.keys())}")
        result = await self._tools[tool_name].run(params)
        log.info(f"Tool result: success={result.get('success')}")
        return result

    def list_tools(self) -> List[dict]:
        return [t.schema() for t in self._tools.values()]

    def schema_str(self) -> str:
        """For injecting into LLM prompts."""
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
            for k, v in t.parameters.items():
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)
