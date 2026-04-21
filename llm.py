"""
LLM Service — Ollama interface
Supports: streaming, general & coder model routing, embeddings
"""

import httpx
import json
import logging
from typing import AsyncGenerator, List

log = logging.getLogger("synapse.llm")


class LLMService:
    def __init__(self, base_url: str, general_model: str, coder_model: str):
        self.base_url = base_url.rstrip("/")
        self.general_model = general_model
        self.coder_model = coder_model
        self._client = httpx.AsyncClient(timeout=120.0)

    # ── Model Selection ───────────────────────────────────────────────────────
    def _pick_model(self, role: str) -> str:
        return self.coder_model if role == "coder" else self.general_model

    # ── Health ────────────────────────────────────────────────────────────────
    async def ping(self) -> bool:
        try:
            r = await self._client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list:
        try:
            r = await self._client.get(f"{self.base_url}/api/tags")
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    # ── Streaming ─────────────────────────────────────────────────────────────
    async def stream(
        self,
        prompt: str,
        role: str = "general",
        system: str = "",
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        model = self._pick_model(role)
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            async with self._client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log.error(f"Stream error: {e}")
            yield f"\n[ERROR: {e}]"

    # ── Complete (non-streaming) ──────────────────────────────────────────────
    async def complete(
        self,
        prompt: str,
        role: str = "general",
        system: str = "",
        temperature: float = 0.7,
    ) -> str:
        full = ""
        async for token in self.stream(prompt, role, system, temperature):
            full += token
        return full.strip()

    # ── Chat (messages format) ────────────────────────────────────────────────
    async def chat_stream(
        self,
        messages: List[dict],
        role: str = "general",
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        model = self._pick_model(role)
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        try:
            async with self._client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log.error(f"Chat stream error: {e}")
            yield f"\n[ERROR: {e}]"

    async def chat(
        self,
        messages: List[dict],
        role: str = "general",
        system: str = "",
    ) -> str:
        full = ""
        async for token in self.chat_stream(messages, role, system):
            full += token
        return full.strip()

    # ── Embeddings ────────────────────────────────────────────────────────────
    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector via Ollama's /api/embeddings endpoint."""
        payload = {"model": "nomic-embed-text", "prompt": text}
        try:
            r = await self._client.post(
                f"{self.base_url}/api/embeddings", json=payload, timeout=30.0
            )
            data = r.json()
            return data.get("embedding", [])
        except Exception as e:
            log.error(f"Embed error: {e}")
            return []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            vec = await self.embed(t)
            results.append(vec)
        return results
