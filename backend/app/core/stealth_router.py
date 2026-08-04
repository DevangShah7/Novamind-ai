"""Stealth router — mask every real backend behind a NovaMind public id.

The chat surface (the UI, the OpenAI-compat endpoint, the
``/api/v1/chat`` endpoint) only ever speaks NovaMind names. The
real backend is whatever the operator wired up in ``alias_config``
(default: Ollama with a generic model id). The router:

1. Picks a real backend at request time (Ollama if reachable, else
   the local rule engine as a silent last-resort fallback).
2. Delegates the actual generation to that backend.
3. Rewrites the returned ``LLMResponse`` so the public id is what
   flows back to the wire — ``model_name`` field, the streaming
   SSE ``model:`` field, and the chat-message metadata all carry
   the brand.
4. Strips private metadata keys (``engine``, ``engine_type``,
   ``requested_model``, ``fallback_reason``, ``handler``,
   ``use_case``) so the response never hints at the underlying
   engine.

The router is intentionally a thin wrapper: it does not stream
tokens itself, it just yields whatever the backend yields. That
keeps the streaming behaviour identical to talking to the backend
directly, and the SSE wrapper in ``v1_compat.py`` reads
``service.model_name`` on every chunk — which is set to the public
id on the router, so every chunk's ``model:`` field is correct
without further plumbing.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from .llm_service import (
    BaseLLMService,
    LLMMessage,
    LLMResponse,
    LLMMessageType,
)

logger = logging.getLogger(__name__)


# Keys that hint at the underlying engine. Stripped from the response
# metadata before it leaves the wire so the public surface never admits
# which model or rule engine powered the reply.
_PRIVATE_METADATA_KEYS = frozenset(
    {
        "engine",
        "engine_type",
        "requested_model",
        "fallback_reason",
        "model",  # we re-add a sanitized "model" key below
        "handler",
        "use_case",
        "processed_by",
    }
)


class StealthRouter(BaseLLMService):
    """Public-id -> real-backend wrapper. All chat goes through here."""

    public_id: str
    backend_model: Optional[str]

    def __init__(self, public_id: str, backend_model: Optional[str] = None):
        # Setting ``self.model_name`` here is critical: the SSE wrapper
        # in v1_compat.py reads ``getattr(service, "model_name", model)``
        # on every chunk, so the public id is what appears on the wire
        # for both streaming and non-streaming responses.
        super().__init__(model_name=public_id)
        self.public_id = public_id
        self.backend_model = backend_model

    # ------------------------------------------------------------------
    # Internal — pick the real backend
    # ------------------------------------------------------------------

    def _resolve_backend(self) -> BaseLLMService:
        """Pick the real backend for this request.

        Order of preference:
          1. A pinned ``OllamaChatService(backend_model)`` — if Ollama
             is reachable AND we have a backend model name.
          2. A generic Ollama service (operator's default) — if Ollama
             is reachable and we don't have a pinned backend.
          3. ``NovaMindLocal`` — silent last-resort fallback when the
             real backend is unreachable. The user gets a generic
             "having trouble" message, not a rule-engine admission.
        """
        # Local imports: avoid a circular import; ollama_service /
        # local_engine pull from llm_service at import time.
        from .ollama_service import OllamaChatService, ollama_reachable, select_default_ollama_model
        from .local_engine import NovaMindLocal

        if ollama_reachable():
            chosen = self.backend_model or select_default_ollama_model()
            try:
                return OllamaChatService(model_name=chosen)
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("StealthRouter: failed to construct OllamaChatService(%s): %s", chosen, e)
        logger.info("StealthRouter: Ollama unreachable, falling back to NovaMindLocal for %s", self.public_id)
        return NovaMindLocal()

    # ------------------------------------------------------------------
    # Internal — sanitize the response shape
    # ------------------------------------------------------------------

    def _stamp(self, response: LLMResponse) -> LLMResponse:
        """Rewrite the response so the public id is what flows back.

        * ``model_name`` becomes the public id.
        * ``metadata`` is reduced to a public-safe dict: only the
          brand ``model`` key plus token-usage and elapsed-ms stats.
        * If the backend returned empty / unknown content, fall back
          to a generic message so the user never sees "I'm a rule
          engine" copy.
        """
        # 1. Brand the model name.
        response.model_name = self.public_id

        # 2. Sanitize metadata.
        original_meta = dict(response.metadata or {})
        safe_meta: Dict[str, Any] = {
            "model": self.public_id,
        }
        # Only carry through numerically-meaningful, non-engine stats.
        for key in ("tokens_used", "elapsed_ms", "tokens_prompt", "tokens_completion"):
            if key in original_meta and original_meta[key] is not None:
                safe_meta[key] = original_meta[key]
        response.metadata = safe_meta

        # 3. Guard against empty content (the streaming path may yield
        # nothing if the backend is unhealthy).
        if not (response.content or "").strip():
            response.content = (
                "I'm having trouble reaching the model right now. "
                "Please try again in a moment."
            )
            response.message_type = LLMMessageType.TEXT
            if not response.metadata:
                response.metadata = {"model": self.public_id}
        return response

    # ------------------------------------------------------------------
    # Public contract — async generation
    # ------------------------------------------------------------------

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        backend = self._resolve_backend()
        try:
            response = await backend.generate_response(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("StealthRouter: backend %s raised %s", type(backend).__name__, e)
            response = LLMResponse(
                content=(
                    "I'm having trouble reaching the model right now. "
                    "Please try again in a moment."
                ),
                message_type=LLMMessageType.TEXT,
                metadata={"model": self.public_id},
                model_name=self.public_id,
            )
        return self._stamp(response)

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        backend = self._resolve_backend()
        try:
            async for chunk in backend.generate_response_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                # Yield the chunk verbatim. The SSE wrapper in
                # v1_compat.py stamps the public id on every chunk
                # via ``service.model_name`` — we set that to the
                # public id in __init__, so nothing else to do here.
                if chunk:
                    yield chunk
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("StealthRouter: streaming backend %s raised %s", type(backend).__name__, e)
            yield (
                "I'm having trouble reaching the model right now. "
                "Please try again in a moment."
            )
