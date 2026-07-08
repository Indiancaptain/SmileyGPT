"""
Unit tests for the memory service. Chroma/sentence-transformers are heavy
optional dependencies, so these tests fake out the module-level client and
embedder rather than requiring the real ML stack to be installed.
"""
import app.services.memory_service as mem_module
from app.services.memory_service import MemoryService


class _FakeCollection:
    def __init__(self):
        self.docs = []

    def add(self, documents, metadatas, ids):
        self.docs.append({"documents": documents, "metadatas": metadatas, "ids": ids})

    def count(self):
        return len(self.docs)

    def query(self, query_texts, n_results):
        # Return whatever was stored, most-recent-first, capped at n_results
        flat = [d["documents"][0] for d in reversed(self.docs)][:n_results]
        return {"documents": [flat]}


async def test_add_and_retrieve_memory_when_available(monkeypatch):
    fake_collection = _FakeCollection()
    monkeypatch.setattr(mem_module, "_chroma_available", True)
    monkeypatch.setattr(mem_module, "_collection_for", lambda user_id: fake_collection)

    await MemoryService.add_memory("user-1", "User loves hiking in Yosemite", {"message_id": "m1"})
    results = await MemoryService.retrieve("user-1", "outdoor hobbies", top_k=5)

    assert results == ["User loves hiking in Yosemite"]


async def test_retrieve_returns_empty_list_for_new_user(monkeypatch):
    monkeypatch.setattr(mem_module, "_chroma_available", True)
    monkeypatch.setattr(mem_module, "_collection_for", lambda user_id: _FakeCollection())

    results = await MemoryService.retrieve("brand-new-user", "anything")
    assert results == []


async def test_memory_disabled_when_chroma_unavailable(monkeypatch):
    monkeypatch.setattr(mem_module, "_chroma_available", False)

    # Should be no-ops, not exceptions, even though no collection exists
    await MemoryService.add_memory("user-2", "some fact", {"message_id": "m2"})
    results = await MemoryService.retrieve("user-2", "some fact")
    assert results == []


async def test_add_memory_failure_is_caught_not_raised(monkeypatch):
    def _boom(user_id):
        raise RuntimeError("simulated Chroma outage")

    monkeypatch.setattr(mem_module, "_chroma_available", True)
    monkeypatch.setattr(mem_module, "_collection_for", _boom)

    # Should log and swallow the error rather than propagate to the caller
    await MemoryService.add_memory("user-3", "text", {"message_id": "m3"})


async def test_retrieve_failure_returns_empty_list(monkeypatch):
    def _boom(user_id):
        raise RuntimeError("simulated Chroma outage")

    monkeypatch.setattr(mem_module, "_chroma_available", True)
    monkeypatch.setattr(mem_module, "_collection_for", _boom)

    results = await MemoryService.retrieve("user-4", "text")
    assert results == []
