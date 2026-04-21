"""
Memory Service — ChromaDB Vector Memory
Semantic storage & retrieval for conversations and knowledge.
"""
import uuid, time, logging, asyncio
from typing import List, Optional
from pathlib import Path

log = logging.getLogger("synapse.memory")


class MemoryService:
    def __init__(self, chroma_path: str, embedding_model: str = "nomic-embed-text"):
        self.chroma_path = chroma_path
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._knowledge = None

    # ── Init ──────────────────────────────────────────────────────────────────
    async def init(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_sync)
        log.info("✅ Memory Service initialized")

    def _init_sync(self):
        import chromadb
        from chromadb.config import Settings
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="conversations", metadata={"hnsw:space": "cosine"},
        )
        self._knowledge = self._client.get_or_create_collection(
            name="knowledge", metadata={"hnsw:space": "cosine"},
        )
        log.info(f"Collections: conv={self._collection.count()} knowledge={self._knowledge.count()}")

    # ── Save ──────────────────────────────────────────────────────────────────
    async def save(self, text: str, metadata: Optional[dict] = None,
                   collection: str = "conversations") -> str:
        doc_id = str(uuid.uuid4())
        meta = {"timestamp": time.time(), "session_id": "default", **(metadata or {})}
        col = self._get_collection(collection)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: col.add(documents=[text], metadatas=[meta], ids=[doc_id])
        )
        return doc_id

    # ── Search ────────────────────────────────────────────────────────────────
    async def search(self, query: str, n: int = 5,
                     collection: str = "conversations",
                     session_id: Optional[str] = None) -> List[dict]:
        col = self._get_collection(collection)
        if col.count() == 0:
            return []
        where = {"session_id": session_id} if session_id else None
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None,
                lambda: col.query(
                    query_texts=[query],
                    n_results=min(n, col.count()),
                    where=where,
                    include=["documents", "metadatas", "distances"],
                ),
            )
        except Exception as e:
            log.error(f"Search error: {e}")
            return []

        memories = []
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for text, meta, dist in zip(docs, metas, dists):
            relevance = round(1.0 - float(dist), 4)
            if relevance > 0.3:
                memories.append({"text": text, "metadata": meta, "relevance": relevance})
        return memories

    # ── Knowledge ─────────────────────────────────────────────────────────────
    async def save_knowledge(self, text: str, topic: str = "general") -> str:
        return await self.save(text, {"type": "knowledge", "topic": topic}, collection="knowledge")

    async def search_knowledge(self, query: str, n: int = 5) -> List[dict]:
        return await self.search(query, n=n, collection="knowledge")

    # ── List Session ──────────────────────────────────────────────────────────
    async def list_session(self, session_id: str, limit: int = 20) -> List[dict]:
        col = self._collection
        if col.count() == 0:
            return []
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None,
                lambda: col.get(
                    where={"session_id": session_id},
                    include=["documents", "metadatas"],
                    limit=limit,
                ),
            )
            docs  = results.get("documents", [])
            metas = results.get("metadatas", [])
            items = [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
            items.sort(key=lambda x: x["metadata"].get("timestamp", 0), reverse=True)
            return items
        except Exception as e:
            log.error(f"List error: {e}")
            return []

    # ── Clear ─────────────────────────────────────────────────────────────────
    async def clear(self, session_id: Optional[str] = None):
        loop = asyncio.get_running_loop()
        if session_id:
            try:
                results = await loop.run_in_executor(
                    None,
                    lambda: self._collection.get(where={"session_id": session_id}, include=[]),
                )
                ids = results.get("ids", [])
                if ids:
                    await loop.run_in_executor(None, lambda: self._collection.delete(ids=ids))
                log.info(f"Cleared {len(ids)} memories for session {session_id}")
            except Exception as e:
                log.error(f"Clear error: {e}")
        else:
            def _reset():
                self._client.delete_collection("conversations")
                self._collection = self._client.get_or_create_collection(
                    name="conversations", metadata={"hnsw:space": "cosine"}
                )
            await loop.run_in_executor(None, _reset)
            log.info("Cleared all conversation memory")

    # ── Stats ─────────────────────────────────────────────────────────────────
    async def collection_count(self) -> dict:
        return {
            "conversations": self._collection.count() if self._collection else 0,
            "knowledge":     self._knowledge.count()  if self._knowledge  else 0,
        }

    # ── Helper ────────────────────────────────────────────────────────────────
    def _get_collection(self, name: str):
        return self._knowledge if name == "knowledge" else self._collection
