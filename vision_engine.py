"""
Vision Engine — Image Understanding via Ollama (llava / bakllava / moondream)
Supports: image description, OCR, visual Q&A, code-from-screenshot
"""

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import httpx

log = logging.getLogger("synapse.vision")

VISION_MODELS = ["llava", "llava:13b", "llava:7b", "bakllava", "moondream"]

VISION_TASKS = {
    "describe":  "Describe this image in detail. Be specific about objects, colors, text, layout.",
    "ocr":       "Extract ALL text visible in this image exactly as written. Format it clearly.",
    "analyze":   "Analyze this image. What is the key information, data, or message it conveys?",
    "code":      "This is a screenshot of code or a diagram. Extract and reproduce the content exactly.",
    "qa":        "",   # user provides the question
    "ui":        "Describe this UI/interface screenshot. List all visible elements, buttons, text, and layout.",
    "data":      "Extract all data, numbers, and information from this chart, table, or diagram.",
}


class VisionEngine:
    def __init__(self, ollama_base_url: str):
        self.base_url  = ollama_base_url.rstrip("/")
        self._client   = httpx.AsyncClient(timeout=120.0)
        self._model    = None  # auto-detected

    # ── Model Detection ───────────────────────────────────────────────────────
    async def detect_vision_model(self) -> Optional[str]:
        """Find an installed vision model."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            for vm in VISION_MODELS:
                for m in models:
                    if vm.lower() in m.lower():
                        self._model = m
                        log.info(f"Vision model detected: {m}")
                        return m
        except Exception as e:
            log.error(f"Vision model detect error: {e}")
        return None

    async def _get_model(self) -> Optional[str]:
        if self._model:
            return self._model
        return await self.detect_vision_model()

    # ── Analyse Image ─────────────────────────────────────────────────────────
    async def analyse(self, image_data: bytes, task: str = "describe",
                      question: str = "") -> Dict:
        """Analyse an image with a vision model."""
        model = await self._get_model()
        if not model:
            return {"success": False,
                    "error": "No vision model installed. Run: ollama pull llava"}

        b64 = base64.b64encode(image_data).decode("utf-8")
        prompt = VISION_TASKS.get(task, task)
        if task == "qa" and question:
            prompt = question
        elif question:
            prompt = f"{prompt}\n\nAdditional question: {question}"

        try:
            payload = {
                "model":  model,
                "prompt": prompt or "Describe this image.",
                "images": [b64],
                "stream": False,
            }
            resp = await self._client.post(
                f"{self.base_url}/api/generate", json=payload, timeout=90.0
            )
            data = resp.json()
            result = data.get("response", "").strip()
            return {"success": True, "model": model, "task": task,
                    "result": result, "prompt": prompt}
        except Exception as e:
            log.error(f"Vision analyse error: {e}")
            return {"success": False, "error": str(e)}

    async def analyse_stream(self, image_data: bytes, task: str = "describe",
                             question: str = "") -> AsyncGenerator[str, None]:
        model = await self._get_model()
        if not model:
            yield "❌ No vision model installed. Run: `ollama pull llava`"
            return

        b64 = base64.b64encode(image_data).decode("utf-8")
        prompt = VISION_TASKS.get(task, task)
        if task == "qa" and question:
            prompt = question
        elif question:
            prompt = f"{prompt}\n\nQuestion: {question}"

        try:
            payload = {
                "model":  model,
                "prompt": prompt or "Describe this image.",
                "images": [b64],
                "stream": True,
            }
            async with self._client.stream(
                "POST", f"{self.base_url}/api/generate",
                json=payload, timeout=90.0
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                        if d.get("response"):
                            yield d["response"]
                        if d.get("done"):
                            break
                    except Exception:
                        continue
        except Exception as e:
            yield f"\n[Vision error: {e}]"

    # ── URL Image ─────────────────────────────────────────────────────────────
    async def analyse_url(self, url: str, task: str = "describe",
                          question: str = "") -> Dict:
        """Download an image from URL then analyse."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP {resp.status_code}"}
                ct = resp.headers.get("content-type", "")
                if "image" not in ct:
                    return {"success": False, "error": "URL is not an image"}
                return await self.analyse(resp.content, task, question)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Available tasks ───────────────────────────────────────────────────────
    def available_tasks(self) -> Dict[str, str]:
        return VISION_TASKS

    def is_available(self) -> bool:
        return self._model is not None
