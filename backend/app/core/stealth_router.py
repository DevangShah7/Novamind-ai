"""StealthRouter — NovaMind's public-facing chat service.

Wraps a real backend (Ollama today) so every response carries the
*public* NovaMind model id (``NovaMind-Chat``, ``NovaMind-Pro``,
``NovaMind-Code``) on the wire — never the real engine or real
model name. The goal is a single chat surface that always speaks
"NovaMind", regardless of which model is actually generating.

The wrapper sits at the same level as ``OllamaChatService`` and
``NovaMindLocal``: it implements ``BaseLLMService`` so the chat
endpoints, the OpenAI-compatible surface, and the developer
playground can address it transparently. ``get_llm_service()`` always
returns one of these for the in-app chat path.

The backend model id (e.g. ``qwen2.5-coder:14b``) is read from
``alias_config.backend_for(public_id)`` and resolved at construction
time so a misconfigured public id never reaches the wire.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from .alias_config import backend_for
from .llm_service import (
    BaseLLMService,
    LLMMessage,
    LLMMessageType,
    LLMResponse,
)
from .ollama_service import OllamaChatService, ollama_reachable

logger = logging.getLogger(__name__)


# Keys that must never reach the wire in ``LLMResponse.metadata``.
# These describe internals (which engine ran, what fallback chain
# fired, what the user actually requested) and would let a curious
# caller infer the real model.
_PRIVATE_METADATA_KEYS = frozenset({
    "engine",
    "engine_type",
    "requested_model",
    "fallback_reason",
    "model",          # the *real* backend model id leaks through here today
    "handler",        # rule-engine only — still leaks internals
    "use_case",       # rule-engine only — same reason
    "processed_by",   # NeuraX template classes stamp this
})


def _sanitize(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a public-safe copy of ``metadata``.

    ``tokens_used`` and any other future safe keys are preserved. The
    private keys above are stripped so the JSON returned by the
    chat endpoints and the row stored in the chat_messages table
    never carry internals.
    """
    if not metadata:
        return {}
    return {k: v for k, v in metadata.items() if k not in _PRIVATE_METADATA_KEYS}


class StealthRouter(BaseLLMService):
    """Public NovaMind model that delegates to a real engine.

    Construction is cheap — it just stores the public id and resolves
    the backend model name from ``alias_config``. The real backend
    service is instantiated lazily on the first ``generate_response``
    call so a cold start that only lists models doesn't pay any
    network cost.
    """

    def __init__(self, public_id: str):
        super().__init__(model_name=public_id)
        self.public_id = public_id
        self.backend_model = backend_for(public_id) or public_id
        # ``self.model_name`` is what the SSE wrapper reads in
        # ``v1_compat.py.chat_completions`` for every streaming chunk,
        # so it MUST stay as the public id. ``_run_complete`` and
        # ``generate_response_stream`` don't touch it — only the
        # backend service gets the real name.
        self._backend: Optional[BaseLLMService] = None

    # ----- backend resolution -----

    def _resolve_backend(self) -> BaseLLMService:
        """Return a fresh backend service for the current request.

        Picks ``OllamaChatService`` when reachable; otherwise the
        rule engine. The rule engine copy has been rewritten (see
        ``local_engine._default_fallback``) so its no-match message
        doesn't admit to being rule-based — the stealth layer
        preserves that lie by overriding ``model_name`` and
        sanitising metadata.
        """
        if self._backend is not None:
            return self._backend
        if ollama_reachable():
            self._backend = OllamaChatService(model_name=self.backend_model)
        else:
            from .local_engine import NovaMindLocal
            self._backend = NovaMindLocal(model_name=self.public_id)
        return self._backend

    # ----- response rewriting -----

    def _stamp(self, response: LLMResponse) -> LLMResponse:
        """Rewrite an ``LLMResponse`` so the wire only sees the public id.

        The ``model_name`` on the response is what the chat endpoint
        and the developer-facing ``/v1/chat/completions`` response
        surface — overwrite it with ``self.public_id``. Metadata is
        stripped to public-safe keys via ``_sanitize``; tokens_used
        is preserved because billing needs it.
        """
        response.model_name = self.public_id
        response.metadata = _sanitize(response.metadata)
        # Always stamp a stable ``model`` key so downstream readers
        # (chat_message meta_data, /v1/billing rollups) have something
        # consistent to group by. This is the *public* id by design.
        response.metadata["model"] = self.public_id
        return response

    # ----- BaseLLMService contract -----

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        backend = self._resolve_backend()
        response = await backend.generate_response(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return self._stamp(response)

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        # The streamed text is identical regardless of public id —
        # the user sees the same answer whether they picked
        # ``NovaMind-Chat`` or ``NovaMind-Pro``. The SSE wrapper in
        # ``v1_compat.py`` reads ``self.model_name`` for each chunk,
        # so as long as ``self.model_name == self.public_id`` (set
        # in ``__init__``), the wire stays clean. The backend
        # service's own ``self.model_name`` is the *real* model id
        # but never appears on the wire — only the chunks do.
        backend = self._resolve_backend()
        async for chunk in backend.generate_response_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk