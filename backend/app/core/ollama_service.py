"""
Ollama HTTP client — OpenAI-compatible surface at http://localhost:11434/v1.

Used by /v1/chat/completions and /v1/models so the developer-facing API can
route to a real foundation model when Ollama is reachable. Falls back to
NovaMindLocal (in-process rule-based engine) when Ollama is not running,
so the rest of the app never breaks.

We never silently swap a real model for the local engine: callers can
detect the fallback by inspecting ``response.metadata.engine`` in the
returned ``LLMResponse``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .llm_service import (
    BaseLLMService,
    LLMMessage,
    LLMMessageType,
    LLMResponse,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "120"))


def ollama_reachable(timeout_s: float = 1.5) -> bool:
    """Cheap connectivity probe — used by /v1/models to filter the listing."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def ollama_list_models() -> List[Dict[str, Any]]:
    """Return the OpenAI-style list payload from Ollama, or [] if unreachable."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/v1/models", timeout=2.0)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.debug("ollama_list_models failed: %s", e)
        return []


def _to_openai_messages(messages: List[Any]) -> List[Dict[str, str]]:
    """Convert chat history into the OpenAI `{role, content}` shape.

    Tolerates both ``LLMMessage`` instances and pre-shaped dicts
    (``{"role": ..., "content": ...}``). The dict form is convenient for
    callers that don't need full ``LLMMessage`` semantics — e.g. the
    file-outline generators in ``app/api/endpoints/files.py`` that only
    ever send a single user turn. Defending against the dict form here
    keeps a stray call from crashing the whole stealth-router path with
    ``AttributeError: 'dict' object has no attribute 'is_ai'`` and
    returning the canned "having trouble reaching the model" reply.
    """
    out: List[Dict[str, str]] = []
    for m in messages:
        # Dict form: trust the caller, just forward role/content.
        if isinstance(m, dict):
            role = m.get("role") or "user"
            content = m.get("content") or ""
            if content:
                out.append({"role": role, "content": content})
            continue
        # LLMMessage form: derive role from is_ai.
        role = "assistant" if getattr(m, "is_ai", False) else "user"
        content = getattr(m, "content", "") or ""
        if content:
            out.append({"role": role, "content": content})
    return out


class OllamaChatService(BaseLLMService):
    """Routes chat-completion requests to a local Ollama instance.

    Implements the same BaseLLMService interface as NovaMindLocal so callers
    (the chat endpoint, the developer API) don't have to know which engine
    they're talking to.
    """

    def __init__(self, model_name: str = "llama3.2:3b"):
        super().__init__(model_name=model_name)
        self.base_url = OLLAMA_BASE_URL
        self.timeout_s = OLLAMA_TIMEOUT_S

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": _to_openai_messages(messages),
            "temperature": float(temperature),
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
            r.raise_for_status()
            data = r.json()
        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            # Let timeouts propagate so the chat endpoint can return a clean 504
            # (vs swallowing it into the local-engine fallback and giving the
            # user a fake "AI" answer when Ollama is actually unreachable).
            raise
        except Exception as e:
            logger.warning(
                "Ollama call failed (%s) — falling back to NovaMindLocal", e
            )
            from .local_engine import NovaMindLocal
            local_resp = await NovaMindLocal().generate_response(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            )
            # Re-stamp metadata so callers can tell "asked Ollama, got local"
            # from "asked local directly". The user still gets a sensible
            # answer, but the engine name in the response reveals the
            # degradation so /health and the UI can surface it.
            local_resp.metadata = {
                **(local_resp.metadata or {}),
                "engine": "local_fallback",
                "fallback_reason": f"ollama_error: {type(e).__name__}: {e}",
                "requested_model": self.model_name,
            }
            return local_resp

        elapsed_ms = int((time.time() - t0) * 1000)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = ""
        usage = data.get("usage") or {}
        tokens = usage.get("total_tokens") or len(content.split())

        return LLMResponse(
            content=content,
            message_type=LLMMessageType.TEXT,
            metadata={
                "engine": "ollama",
                "model": data.get("model", self.model_name),
                "elapsed_ms": elapsed_ms,
                "tokens_prompt": usage.get("prompt_tokens"),
                "tokens_completion": usage.get("completion_tokens"),
            },
            model_name=data.get("model", self.model_name),
            tokens_used=int(tokens),
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": _to_openai_messages(messages),
            "temperature": float(temperature),
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                ) as r:
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            import json
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content") or ""
                        except Exception:
                            delta = ""
                        if delta:
                            yield delta
        except (httpx.TimeoutException, asyncio.TimeoutError):
            # See generate_response — propagate so the endpoint can 504 cleanly.
            raise
        except Exception as e:
            logger.warning("Ollama stream failed (%s) — falling back to NovaMindLocal", e)
            from .local_engine import NovaMindLocal
            async for piece in NovaMindLocal().generate_response_stream(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            ):
                yield piece


def select_default_ollama_model() -> str:
    """Pick the first available model, prefer llama3.2:3b if present."""
    for m in ollama_list_models():
        if m.get("id") == "llama3.2:3b":
            return "llama3.2:3b"
    models = ollama_list_models()
    return models[0]["id"] if models else "llama3.2:3b"