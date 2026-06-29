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


def _to_openai_messages(messages: List[LLMMessage]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for m in messages:
        role = "assistant" if m.is_ai else "user"
        if m.content:
            out.append({"role": role, "content": m.content})
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
            logger.warning("Ollama call failed (%s) — falling back to NovaMindLocal", e)
            from .local_engine import NovaMindLocal
            return await NovaMindLocal().generate_response(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            )

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