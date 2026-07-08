"""
LLM abstraction layer. Talks to any OpenAI-compatible chat completions
endpoint, which means swapping LLM_BASE_URL lets this run against OpenAI,
Groq, local Ollama (with an OpenAI-compat shim), etc. without code changes.
"""
from typing import AsyncGenerator, List, Optional

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

client = AsyncOpenAI(api_key=settings.LLM_API_KEY or "not-set", base_url=settings.LLM_BASE_URL)

# Only transient, connection-level failures are worth retrying. Once a
# stream has actually started emitting tokens we never retry — replaying
# it would duplicate content the client has already rendered.
_RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)


class LLMService:
    @staticmethod
    def resolve_model(requested: Optional[str], has_images: bool = False) -> str:
        """Explicit, valid user choices always win — including for image
        requests, since every model in AVAILABLE_MODELS is expected to be
        vision-capable. LLM_VISION_MODEL is only a fallback default when no
        valid model was requested."""
        if requested and requested in settings.AVAILABLE_MODELS:
            return requested
        return settings.LLM_VISION_MODEL if has_images else settings.LLM_DEFAULT_MODEL

    @staticmethod
    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def _start_stream(model: str, messages: List[dict]):
        return await client.chat.completions.create(model=model, messages=messages, stream=True, temperature=0.7)

    @staticmethod
    async def stream_chat(
        messages: List[dict],
        model: Optional[str] = None,
        has_images: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Yields incremental text tokens from the model."""
        resolved_model = LLMService.resolve_model(model, has_images=has_images)

        if not settings.LLM_API_KEY:
            # Graceful degradation when no API key is configured, so the
            # rest of the stack (UI, DB, streaming plumbing) is still
            # demonstrable without external credentials.
            fallback = (
                "[SmileyGPT] No LLM_API_KEY is configured on the server, so I can't "
                "reach a real model right now. Set LLM_API_KEY (and optionally "
                "LLM_BASE_URL) in your environment to enable live responses."
            )
            for word in fallback.split(" "):
                yield word + " "
            return

        try:
            stream = await LLMService._start_stream(resolved_model, messages)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"LLM connection failed after retries: {exc}")
            yield f"\n\n[Error contacting model: {exc}]"
            return

        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as exc:  # noqa: BLE001
            # Mid-stream failure: some tokens may already be with the client,
            # so we surface the error inline rather than retrying from scratch.
            logger.error(f"LLM streaming interrupted: {exc}")
            yield f"\n\n[Error contacting model: {exc}]"


llm_service = LLMService()
