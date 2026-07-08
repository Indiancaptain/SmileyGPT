"""
Unit tests for LLMService. The real OpenAI client is monkeypatched so
these tests run without network access or a real API key.
"""
import os

import pytest
from openai import APIConnectionError

import app.services.llm_service as llm_module
from app.services.llm_service import LLMService


# ---------- resolve_model routing ----------

def test_resolve_model_uses_valid_requested_model():
    assert LLMService.resolve_model("gpt-4o") == "gpt-4o"


def test_resolve_model_falls_back_to_default_for_unknown_model():
    assert LLMService.resolve_model("not-a-real-model") == "gpt-4o-mini"


def test_resolve_model_falls_back_to_default_when_none_requested():
    assert LLMService.resolve_model(None) == "gpt-4o-mini"


def test_resolve_model_respects_explicit_choice_even_with_images():
    # A valid explicit model choice should NOT be silently overridden just
    # because the request includes images.
    assert LLMService.resolve_model("gpt-4o", has_images=True) == "gpt-4o"


def test_resolve_model_uses_vision_default_when_no_valid_model_and_has_images():
    assert LLMService.resolve_model("bogus-model", has_images=True) == "gpt-4o-mini"


# ---------- stream_chat: no API key configured (degraded mode) ----------

async def test_stream_chat_without_api_key_yields_fallback_message(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "LLM_API_KEY", "")
    tokens = [t async for t in LLMService.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(tokens)
    assert "No LLM_API_KEY" in "".join(tokens)


# ---------- stream_chat: successful streaming ----------

class _FakeChunk:
    def __init__(self, text):
        self.choices = [type("C", (), {"delta": type("D", (), {"content": text})()})]


class _FakeStream:
    def __init__(self, tokens):
        self._tokens = tokens

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for t in self._tokens:
            yield _FakeChunk(t)


async def test_stream_chat_yields_tokens_from_provider(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "LLM_API_KEY", "fake-key-for-test")

    async def fake_start_stream(model, messages):
        return _FakeStream(["Hello", " ", "world"])

    monkeypatch.setattr(LLMService, "_start_stream", fake_start_stream)

    tokens = [t async for t in LLMService.stream_chat([{"role": "user", "content": "hi"}], model="gpt-4o-mini")]
    assert tokens == ["Hello", " ", "world"]


# ---------- stream_chat: connection failure surfaces a clean error ----------

async def test_stream_chat_reports_error_after_connection_failure(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "LLM_API_KEY", "fake-key-for-test")

    async def always_fails(model, messages):
        raise APIConnectionError(request=None)

    monkeypatch.setattr(LLMService, "_start_stream", always_fails)

    tokens = [t async for t in LLMService.stream_chat([{"role": "user", "content": "hi"}])]
    joined = "".join(tokens)
    assert "Error contacting model" in joined


async def test_start_stream_actually_retries_transient_failures(monkeypatch):
    """Patches one level deeper than _start_stream (the raw OpenAI client
    call) so the @retry decorator on _start_stream itself is exercised,
    not bypassed."""
    call_count = {"n": 0}

    async def flaky_create(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise APIConnectionError(request=None)
        return _FakeStream(["recovered"])

    monkeypatch.setattr(llm_module.client.chat.completions, "create", flaky_create)

    stream = await LLMService._start_stream("gpt-4o-mini", [{"role": "user", "content": "hi"}])
    tokens = [chunk.choices[0].delta.content async for chunk in stream]

    assert call_count["n"] == 3  # failed twice, succeeded on the 3rd attempt
    assert tokens == ["recovered"]
