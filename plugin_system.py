"""
Plugin System — Dynamic Package Manager & Plugin Registry
AI can discover, install, validate, and use Python packages at runtime.
Plugins extend the ToolRegistry with auto-generated wrappers.
"""

import ast
import asyncio
import importlib
import json
import logging
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.plugins")

PLUGINS_DIR = Path("./data/plugins")
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

REGISTRY_FILE = PLUGINS_DIR / "registry.json"

# Curated safe packages that AI can auto-install
ALLOWED_PACKAGES = {
    # Data & Science
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
    "scikit-learn", "statsmodels", "sympy", "networkx",
    # NLP
    "nltk", "spacy", "textblob", "fuzzywuzzy", "thefuzz",
    "langdetect", "chardet", "ftfy",
    # Web & APIs
    "beautifulsoup4", "lxml", "requests", "aiohttp", "feedparser",
    "selenium", "playwright",
    # File Processing
    "pillow", "pdf2image", "tabula-py", "openpyxl", "xlrd",
    "python-docx", "python-pptx", "pypdf2",
    # Utilities
    "arrow", "humanize", "tqdm", "rich", "click",
    "pyyaml", "toml", "jsonschema", "python-dotenv",
    "cryptography", "qrcode", "barcode",
    # Code
    "black", "isort", "pylint", "mypy", "bandit",
    "tree-sitter", "pygments",
    # AI/ML
    "sentence-transformers", "transformers", "torch",
    "openai", "anthropic", "cohere",
}

WRAPPER_SYSTEM = """You are a Python wrapper generator.
Given a package name and its capabilities, write a Tool wrapper class.

Rules:
- Class inherits ToolBase (already in scope)
- name = "pkg_name_action" (snake_case)
- description = one clear sentence
- parameters = dict of param descriptions
- async def run(self, params: dict) -> dict
- Always return {"success": bool, ...}
- Import the package inside run() — not at module level
- Catch ALL exceptions

Write ONLY the class, no markdown fences, no imports outside run()."""


@dataclass
class Plugin:
    plugin_id:   str
    name:        str
    package:     str
    version:     str
    description: str
    capabilities: List[str]
    installed_at: float
    tool_count:  int
    enabled:     bool = True
    auto_installed: bool = False


class PluginSystem:
    def __init__(self, llm, tool_registry, capability_engine):
        self.llm       = llm
        self.registry  = tool_registry
        self.capability = capability_engine
        self._plugins: Dict[str, Plugin] = {}
        self._load_registry()

    # ── Registry Persistence ──────────────────────────────────────────────────
    def _load_registry(self):
        if REGISTRY_FILE.exists():
            try:
                data = json.loads(REGISTRY_FILE.read_text())
                for d in data:
                    self._plugins[d["package"]] = Plugin(**d)
                log.info(f"Plugin System: {len(self._plugins)} plugins loaded")
            except Exception as e:
                log.warning(f"Plugin registry load error: {e}")

    def _save_registry(self):
        data = [asdict(p) for p in self._plugins.values()]
        REGISTRY_FILE.write_text(json.dumps(data, indent=2))

    # ── Check if package is installed ────────────────────────────────────────
    def is_installed(self, package: str) -> bool:
        pkg_norm = package.lower().replace("-", "_")
        try:
            import importlib.util
            return importlib.util.find_spec(pkg_norm) is not None
        except Exception:
            return False

    # ── Install package ───────────────────────────────────────────────────────
    async def install(self, package: str, auto: bool = False) -> Dict:
        """Install a Python package via pip."""
        pkg_norm = package.lower().replace("-", "_")

        # Security check
        if package not in ALLOWED_PACKAGES and pkg_norm not in ALLOWED_PACKAGES:
            return {
                "success": False,
                "error": f"Package '{package}' not in allowed list. Add it to ALLOWED_PACKAGES.",
                "allowed": sorted(list(ALLOWED_PACKAGES))[:20],
            }

        if self.is_installed(package):
            return {"success": True, "message": f"'{package}' already installed", "already_installed": True}

        log.info(f"Installing package: {package}")
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [sys.executable, "-m", "pip", "install", package, "--quiet", "--no-input"],
                    capture_output=True, text=True, timeout=120
                )
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr[:500]}

            # Get installed version
            ver_result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [sys.executable, "-m", "pip", "show", package],
                    capture_output=True, text=True, timeout=10
                )
            )
            version = "unknown"
            for line in ver_result.stdout.splitlines():
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break

            log.info(f"✅ Installed {package}=={version}")
            return {
                "success": True,
                "package": package,
                "version": version,
                "message": f"'{package}' installed successfully",
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timed out (>120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Auto-install + generate tool wrapper ──────────────────────────────────
    async def add_plugin(
        self, package: str, description: str = "",
        auto_generate_tools: bool = True
    ) -> Dict:
        """Install package + auto-generate Tool wrappers."""
        # Install
        inst = await self.install(package)
        if not inst.get("success"):
            return inst

        version = inst.get("version", "?")

        # Generate tool wrappers via LLM
        tools_added = []
        if auto_generate_tools:
            tools_added = await self._generate_tools(package, description)

        plugin = Plugin(
            plugin_id    = uuid.uuid4().hex[:8],
            name         = package,
            package      = package,
            version      = version,
            description  = description or f"Auto-installed plugin: {package}",
            capabilities = [t["name"] for t in tools_added],
            installed_at = time.time(),
            tool_count   = len(tools_added),
            auto_installed = inst.get("already_installed", False),
        )
        self._plugins[package] = plugin
        self._save_registry()

        return {
            "success":     True,
            "plugin_id":   plugin.plugin_id,
            "package":     package,
            "version":     version,
            "tools_added": tools_added,
            "tool_count":  len(tools_added),
        }

    async def _generate_tools(self, package: str, description: str) -> List[Dict]:
        """Use LLM to write Tool wrappers for the package."""
        prompt = (
            f"Package: {package}\n"
            f"Description: {description or 'popular Python library'}\n\n"
            f"Write ONE useful Tool class that wraps a key feature of this package.\n"
            f"The tool should do something concrete and immediately useful.\n"
            f"Inherit from ToolBase (already in scope). No module-level imports.\n"
            f"Write the class:"
        )
        code = await self.llm.complete(
            prompt, role="coder", system=WRAPPER_SYSTEM, temperature=0.3
        )
        code = re.sub(r"```\w*|```", "", code).strip()

        # Try to load and register
        tools_added = []
        try:
            result = await self.capability.create_tool(
                tool_name=f"{package}_tool",
                tool_description=f"Tool powered by {package}",
                tool_purpose=f"Provides {package} capabilities",
                example_params={},
            )
            if result.get("success"):
                tools_added.append({
                    "name": result.get("tool_name"),
                    "package": package,
                })
        except Exception as e:
            log.warning(f"Tool generation for {package} failed: {e}")

        return tools_added

    # ── Uninstall ─────────────────────────────────────────────────────────────
    async def remove_plugin(self, package: str) -> Dict:
        if package not in self._plugins:
            return {"success": False, "error": "Plugin not registered"}

        plugin = self._plugins[package]
        # Remove generated tools
        for cap in plugin.capabilities:
            self.capability.delete_tool(cap)

        # Uninstall package
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", package, "-y"],
                capture_output=True, timeout=30
            )
        )
        del self._plugins[package]
        self._save_registry()
        return {"success": True, "message": f"'{package}' removed"}

    # ── List installed packages ───────────────────────────────────────────────
    async def list_installed(self) -> List[Dict]:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15
            )
        )
        try:
            return json.loads(result.stdout)
        except Exception:
            return []

    def list_plugins(self) -> List[Dict]:
        return [asdict(p) for p in self._plugins.values()]

    def list_allowed(self) -> List[str]:
        return sorted(ALLOWED_PACKAGES)

    def stats(self) -> Dict:
        return {
            "total_plugins": len(self._plugins),
            "total_tools":   sum(p.tool_count for p in self._plugins.values()),
            "allowed_packages": len(ALLOWED_PACKAGES),
        }
