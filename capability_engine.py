"""
Capability Engine — AI writes its own tools dynamically
Detects gaps → generates Python tool class → validates → hot-loads → registers.
"""
import ast, importlib.util, inspect, json, logging, re, time, uuid
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.capability")

CAPABILITIES_DIR = Path("./data/capabilities")
CAPABILITIES_DIR.mkdir(parents=True, exist_ok=True)

TOOL_WRITER_SYSTEM = """You are an expert Python tool developer for an async AI agent system.
Write a single complete Python class.

STRICT RULES:
- Class name must be CamelCase, distinct from any other class
- Must have: name (str), description (str), parameters (dict) as CLASS attributes
- Must have: async def run(self, params: dict) -> dict
- run() ALWAYS returns a dict with key "success" (bool)
- Catch ALL exceptions: return {"success": False, "error": str(e)}
- Only use stdlib modules: asyncio, os, re, json, pathlib, subprocess, hashlib, base64, urllib
- httpx is also allowed for HTTP requests
- NEVER use: eval(), exec(), __import__(), os.system(), sys.exit(), rm -rf

The class must inherit from ToolBase (already injected into scope — do NOT import it).

Output ONLY the Python class code. No markdown fences, no imports (ToolBase already imported)."""

GAP_DETECTOR_SYSTEM = """You are a capability gap analyzer.
Given a user request and existing tools, decide if a NEW tool is needed.
Return ONLY valid JSON — no markdown, no explanation:
{
  "needs_new_tool": true,
  "tool_name": "snake_case_name",
  "tool_description": "one sentence description",
  "tool_purpose": "why this is needed",
  "example_params": {"key": "value"},
  "confidence": 0.85
}
If existing tools are sufficient, return: {"needs_new_tool": false}"""


class ToolBase:
    """Base class all dynamically generated tools must inherit."""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    async def run(self, params: dict) -> dict:
        raise NotImplementedError

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description,
                "parameters": self.parameters}


class CapabilityEngine:
    def __init__(self, llm, tool_registry, memory):
        self.llm      = llm
        self.registry = tool_registry
        self.memory   = memory
        self._creation_log: List[Dict] = []
        self._load_persisted_tools()

    # ── Load persisted tools on startup ──────────────────────────────────────
    def _load_persisted_tools(self):
        count = 0
        for py_file in CAPABILITIES_DIR.glob("tool_*.py"):
            try:
                tool = self._load_tool_from_file(py_file)
                if tool:
                    self.registry._register(tool)
                    count += 1
                    log.info(f"Loaded persisted tool: {tool.name}")
            except Exception as e:
                log.warning(f"Failed to load {py_file.name}: {e}")
        if count:
            log.info(f"Loaded {count} persisted capabilities")

    def _load_tool_from_file(self, path: Path) -> Optional[ToolBase]:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod  = importlib.util.module_from_spec(spec)
        # Inject ToolBase so generated code can inherit it
        mod.ToolBase = ToolBase
        mod.asyncio  = __import__("asyncio")
        mod.os       = __import__("os")
        mod.re       = __import__("re")
        mod.json     = __import__("json")
        mod.Path     = Path
        spec.loader.exec_module(mod)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if (issubclass(obj, ToolBase) and obj is not ToolBase
                    and hasattr(obj, "name") and obj.name):
                return obj()
        return None

    # ── Gap Detection ─────────────────────────────────────────────────────────
    async def detect_capability_gap(self, user_request: str,
                                     failure_reason: str = "") -> Optional[Dict]:
        existing = ", ".join(self.registry._tools.keys())
        prompt = (
            f"Existing tools: {existing}\n"
            f"User request: {user_request}\n"
            f"Gap/failure: {failure_reason or 'task may need a new capability'}"
        )
        raw = await self.llm.complete(
            prompt, role="general", system=GAP_DETECTOR_SYSTEM, temperature=0.2
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            result = json.loads(raw)
            if result.get("needs_new_tool") and result.get("confidence", 0) > 0.6:
                return result
        except Exception as e:
            log.debug(f"Gap detection parse error: {e}")
        return None

    # ── Tool Creation ─────────────────────────────────────────────────────────
    async def create_tool(self, tool_name: str, tool_description: str,
                          tool_purpose: str,
                          example_params: Dict = None) -> Dict:
        log.info(f"Creating tool: {tool_name}")
        prompt = (
            f"Tool name (use as class attribute 'name'): '{tool_name}'\n"
            f"Description (use as 'description' attribute): '{tool_description}'\n"
            f"Purpose: {tool_purpose}\n"
            f"Example params your run() should handle: {json.dumps(example_params or {})}\n\n"
            f"Write the complete Python class inheriting ToolBase:"
        )

        code = ""
        validation = {"valid": False, "error": "Not generated"}
        for attempt in range(1, 4):
            raw = await self.llm.complete(
                prompt, role="coder", system=TOOL_WRITER_SYSTEM, temperature=0.3
            )
            code = self._clean_code(raw)
            validation = self._validate_code(code, tool_name)
            if validation["valid"]:
                break
            log.warning(f"Attempt {attempt} invalid: {validation['error']}")
            prompt += f"\n\nFix this error from previous attempt: {validation['error']}"

        if not validation["valid"]:
            return {"success": False,
                    "error": f"Could not generate valid code: {validation['error']}"}

        # Save to disk
        file_id   = uuid.uuid4().hex[:8]
        save_path = CAPABILITIES_DIR / f"tool_{tool_name}_{file_id}.py"
        save_path.write_text(code)

        # Load and register
        try:
            tool_instance = self._load_tool_from_file(save_path)
            if not tool_instance:
                save_path.unlink()
                return {"success": False, "error": "No valid class found in generated code"}

            self.registry._register(tool_instance)
            entry = {
                "tool_name":   tool_name,
                "description": tool_description,
                "file":        str(save_path),
                "created_at":  time.time(),
                "code_lines":  len(code.splitlines()),
            }
            self._creation_log.append(entry)

            # Remember in knowledge memory
            try:
                await self.memory.save_knowledge(
                    f"AI created tool: {tool_name}. Purpose: {tool_purpose}. "
                    f"Description: {tool_description}.",
                    topic="capability",
                )
            except Exception:
                pass

            log.info(f"✅ Tool registered: {tool_name}")
            return {
                "success":   True,
                "tool_name": tool_name,
                "code":      code,
                "file":      str(save_path),
                "message":   f"Tool '{tool_name}' created and registered successfully",
            }
        except Exception as e:
            save_path.unlink(missing_ok=True)
            return {"success": False, "error": str(e)}

    # ── Auto-Expand (detect + create) ─────────────────────────────────────────
    async def auto_expand(self, user_request: str,
                          failure_reason: str = "") -> Optional[Dict]:
        gap = await self.detect_capability_gap(user_request, failure_reason)
        if not gap:
            return None
        log.info(f"Gap: {gap['tool_name']} — {gap['tool_description']}")
        result = await self.create_tool(
            tool_name=gap["tool_name"],
            tool_description=gap["tool_description"],
            tool_purpose=gap["tool_purpose"],
            example_params=gap.get("example_params", {}),
        )
        result["gap_analysis"] = gap
        return result

    # ── Test a Tool ───────────────────────────────────────────────────────────
    async def test_tool(self, tool_name: str, test_params: Dict) -> Dict:
        result = await self.registry.execute(tool_name, test_params)
        return {"tool": tool_name, "params": test_params,
                "result": result, "passed": result.get("success", False)}

    # ── List / Delete ─────────────────────────────────────────────────────────
    def list_created(self) -> List[Dict]:
        created = []
        for py_file in CAPABILITIES_DIR.glob("tool_*.py"):
            try:
                tool = self._load_tool_from_file(py_file)
                created.append({
                    "name":        tool.name if tool else "?",
                    "description": tool.description if tool else "",
                    "file":        py_file.name,
                    "size":        py_file.stat().st_size,
                })
            except Exception:
                created.append({"name": py_file.stem, "file": py_file.name})
        return created

    def delete_tool(self, tool_name: str) -> bool:
        if tool_name in self.registry._tools:
            del self.registry._tools[tool_name]
        removed = False
        for py_file in CAPABILITIES_DIR.glob(f"tool_{tool_name}_*.py"):
            py_file.unlink()
            removed = True
        return removed

    # ── Validation ────────────────────────────────────────────────────────────
    def _validate_code(self, code: str, expected_name: str) -> Dict:
        if not code.strip():
            return {"valid": False, "error": "Empty code"}
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if not classes:
            return {"valid": False, "error": "No class defined"}

        danger = ["os.system", "eval(", "exec(", "__import__", "sys.exit",
                  "rm -rf", "shutil.rmtree", "format_disk"]
        for d in danger:
            if d in code:
                return {"valid": False, "error": f"Dangerous pattern: {d}"}

        for cls in classes:
            methods = [n.name for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)
                       or isinstance(n, ast.AsyncFunctionDef)]
            if "run" in methods:
                return {"valid": True, "error": None}

        return {"valid": False, "error": "No run() method found"}

    def _clean_code(self, code: str) -> str:
        code = re.sub(r"```python|```py|```", "", code)
        # Remove any standalone 'import ToolBase' lines
        code = re.sub(r"^from core\.tools import.*\n?", "", code, flags=re.MULTILINE)
        code = re.sub(r"^import ToolBase.*\n?", "", code, flags=re.MULTILINE)
        return code.strip()

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        return {
            "total_created":        len(list(CAPABILITIES_DIR.glob("tool_*.py"))),
            "currently_registered": len(self.registry._tools),
            "creation_log":         self._creation_log[-5:],
        }
