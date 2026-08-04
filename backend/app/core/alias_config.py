"""Public NovaMind model alias registry.

The chat UI and the OpenAI-compatible surface both speak a fixed brand
vocabulary (``NovaMind-Chat``, ``NovaMind-Pro``, ``NovaMind-Code``). Behind
each public id sits a real engine + real model — Ollama today, possibly a
managed inference API later. This module is the single source of truth
for that mapping so the wire format never has to mention the underlying
engine by name.

Config is read from the env var ``NOVAMIND_PUBLIC_MODELS``. Two shapes
are accepted:

  1. JSON object — ``NOVAMIND_PUBLIC_MODELS='{"NovaMind-Chat":"qwen2.5-coder:14b"}'``
  2. Inline ``id:backend,id:backend`` list — ``NOVAMIND_PUBLIC_MODELS='NovaMind-Chat:qwen2.5-coder:14b,NovaMind-Pro:qwen2.5-coder:14b'``

The default mapping, when neither is set, ships the three brand ids
pointed at whatever Ollama model the operator has installed locally
(see ``OLLAMA_DEFAULT_MODEL``). Operators can override per-id without
touching code.
"""
from __future__ import annotations

import json
import logging
import os
from threading import Lock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PUBLIC_MODEL = "NovaMind-Chat"

# Fallback when NOVAMIND_PUBLIC_MODELS is unset. We bias toward a generic
# real chat model — the operator can point any of these at a different
# Ollama tag via the env var. ``select_default_ollama_model`` resolves at
# runtime so the user doesn't need to copy-paste the exact tag here.
_FALLBACK_BACKEND_MODEL = "llama3.2:3b"


def _default_mapping() -> Dict[str, str]:
    """Built lazily so ``ollama_service.select_default_ollama_model``
    can run at import time of *its* module without a circular import
    here. The fallback ``_FALLBACK_BACKEND_MODEL`` is the Ollama
    recommended starter; if Ollama is unreachable, the stealth router
    handles it via its own fallback chain.
    """
    try:
        from .ollama_service import select_default_ollama_model
        backend = select_default_ollama_model() or _FALLBACK_BACKEND_MODEL
    except Exception:
        backend = _FALLBACK_BACKEND_MODEL
    return {
        "NovaMind-Chat": backend,
        "NovaMind-Pro": backend,
        "NovaMind-Code": backend,
    }


def _parse_env(raw: str) -> Dict[str, str]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    # JSON object form.
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(
                "NOVAMIND_PUBLIC_MODELS is not valid JSON (%s); ignoring.", e
            )
            return {}
        if not isinstance(obj, dict):
            return {}
        return {str(k): str(v) for k, v in obj.items() if k and v}
    # Inline ``id:backend,id:backend`` form.
    out: Dict[str, str] = {}
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece or ":" not in piece:
            continue
        public_id, _, backend = piece.partition(":")
        public_id = public_id.strip()
        backend = backend.strip()
        if public_id and backend:
            out[public_id] = backend
    return out


_CACHE: Optional[Dict[str, str]] = None
_CACHE_LOCK = Lock()


def _mapping() -> Dict[str, str]:
    """Read the mapping, falling back to defaults. Cached after first
    read because the env var isn't expected to change at runtime.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    with _CACHE_LOCK:
        if _CACHE is not None:
            return _CACHE
        env_raw = os.environ.get("NOVAMIND_PUBLIC_MODELS", "")
        parsed = _parse_env(env_raw)
        merged = _default_mapping()
        merged.update(parsed)  # env wins on collision
        _CACHE = merged
        return _CACHE


def reset_cache() -> None:
    """Test hook — drop the cached mapping so the next call re-reads env."""
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def list_public_ids() -> List[str]:
    """Public ids exposed by ``/api/v1/models`` and ``/v1/models``.

    Order is preserved so the picker renders ``NovaMind-Chat`` first.
    """
    return list(_mapping().keys())


def backend_for(public_id: str) -> Optional[str]:
    """Real backend model name for a public id, or ``None`` if unknown.

    Callers should treat ``None`` as ``"unknown model"`` and route
    through the default public id instead.
    """
    return _mapping().get(public_id)


def default_public_id() -> str:
    """The id the chat endpoint uses when no model is requested.

    ``NovaMind-Chat`` is always first in the default mapping, but if
    an operator customised ``NOVAMIND_PUBLIC_MODELS`` and dropped it,
    we fall back to whatever public id is first in the list.
    """
    ids = list_public_ids()
    if _DEFAULT_PUBLIC_MODEL in ids:
        return _DEFAULT_PUBLIC_MODEL
    return ids[0] if ids else _DEFAULT_PUBLIC_MODEL