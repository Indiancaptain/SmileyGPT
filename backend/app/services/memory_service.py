"""
Long-term memory: stores condensed facts/snippets per user in a local
Chroma collection and retrieves the most relevant ones to inject into
the LLM context window (a lightweight RAG loop).

Chroma is used (over a standalone Qdrant server) because it runs
embedded/persisted-to-disk, keeping the Docker footprint smaller while
remaining a drop-in swap for Qdrant if you need a distributed setup later.
"""
import asyncio
from typing import List

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client = None
_embedder = None
_chroma_available = True

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:  # pragma: no cover - exercised when optional ML deps aren't installed
    _chroma_available = False


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return _embedder


def _collection_for(user_id: str):
    return _get_client().get_or_create_collection(name=f"user_{user_id}", embedding_function=_get_embedder())


def _add_memory_sync(user_id: str, text: str, metadata: dict) -> None:
    col = _collection_for(user_id)
    # Deterministic id from message_id keeps re-runs idempotent (no duplicate
    # memories if a request is retried); falls back to a random id if the
    # caller doesn't provide one so unrelated writes never collide.
    memory_id = metadata.get("message_id") or f"{user_id}-{id(text)}"
    col.add(documents=[text], metadatas=[metadata], ids=[str(memory_id)])


def _retrieve_sync(user_id: str, query: str, top_k: int) -> List[str]:
    col = _collection_for(user_id)
    if col.count() == 0:
        return []
    results = col.query(query_texts=[query], n_results=top_k)
    return results.get("documents", [[]])[0]


class MemoryService:
    """
    Long-term memory backed by Chroma. All methods are async and offload
    the actual (synchronous, CPU/IO-bound) Chroma calls to a worker thread
    via `asyncio.to_thread`, so a slow embedding computation never blocks
    the event loop that's also serving other users' requests.
    """

    @staticmethod
    async def add_memory(user_id: str, text: str, metadata: dict) -> None:
        if not _chroma_available:
            return
        try:
            await asyncio.to_thread(_add_memory_sync, user_id, text, metadata)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Memory write failed: {exc}")

    @staticmethod
    async def retrieve(user_id: str, query: str, top_k: int = None) -> List[str]:
        if not _chroma_available:
            return []
        try:
            return await asyncio.to_thread(_retrieve_sync, user_id, query, top_k or settings.MEMORY_TOP_K)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Memory retrieval failed: {exc}")
            return []


memory_service = MemoryService()
