"""Single source of truth for the public NovaMind model id -> real backend.

The chat surface only ever speaks NovaMind names. Which real model those
names map to is operator-controlled via the ``NOVAMIND_PUBLIC_MODELS``
env var, so swapping the backend (Ollama, a hosted API, a local
weights loader) is a one-line config change with no code edits.

Format
------

The env var accepts either JSON or a compact ``id:backend`` list:

.. code-block:: json

    {"NovaMind-Chat": "llama3.2:3b", "NovaMind-Pro": "llama3.2:3b", "NovaMind-Code": "qwen2.5-coder:14b"}

.. code-block:: text

    NovaMind-Chat:llama3.2:3b,NovaMind-Pro:llama3.2:3b,NovaMind-Code:qwen2.5-coder:14b

Both shapes are equivalent. Bad rows are skipped with a warning so a
typo in one mapping doesn't kill the whole boot.

Public API
----------

``list_public_ids()``  -> ordered list of public ids (the "/api/v1/models" listing)
``backend_for(id)``    -> the real backend model name (or None if unknown)
``default_public_id()`` -> the public id used when the caller doesn't pick one
``reset_cache()``       -> clear the cached parse (used by tests)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Hardcoded defaults. Operators override via NOVAMIND_PUBLIC_MODELS.
# All three ids route to the same backend today — the names are the
# public-facing tier labels, not technical flags.
_DEFAULT_MAPPING: Dict[str, str] = {
    "NovaMind-Chat": "llama3.2:3b",
    "NovaMind-Pro": "llama3.2:3b",
    "NovaMind-Code": "qwen2.5-coder:14b",
}

# Default tier used when the caller doesn't pick (e.g. an old client
# sends no model). Kept constant so tests can pin it.
DEFAULT_PUBLIC_ID: str = "NovaMind-Chat"

_cache: Optional[Dict[str, str]] = None


def _parse_env(raw: str) -> Dict[str, str]:
    """Parse the env var in either JSON or compact form."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    # JSON first.
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if v}
        except json.JSONDecodeError as e:
            logger.warning("NOVAMIND_PUBLIC_MODELS is not valid JSON: %s", e)
    # Compact form: "id:backend,id:backend".
    out: Dict[str, str] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        public_id, backend = chunk.split(":", 1)
        public_id = public_id.strip()
        backend = backend.strip()
        if public_id and backend:
            out[public_id] = backend
    return out


def _mapping() -> Dict[str, str]:
    """Read the env var once and cache the result."""
    global _cache
    if _cache is not None:
        return _cache
    raw = os.environ.get("NOVAMIND_PUBLIC_MODELS", "")
    parsed = _parse_env(raw)
    # Defaults always win unless the env var explicitly overrides them.
    # (Adding a brand-new id should be deliberate.)
    merged = dict(_DEFAULT_MAPPING)
    merged.update(parsed)
    _cache = merged
    return _cache


def reset_cache() -> None:
    """Clear the parsed-mapping cache. Tests use this so they can
    mutate the env var and re-read without spinning up a new process."""
    global _cache
    _cache = None


def list_public_ids() -> List[str]:
    """Public ids in a stable, human-friendly order.

    The order is fixed (default first, then the rest alphabetical) so
    the ``/v1/models`` listing never reshuffles between requests."""
    m = _mapping()
    default = DEFAULT_PUBLIC_ID
    if default not in m:
        return sorted(m.keys())
    rest = sorted(k for k in m.keys() if k != default)
    return [default] + rest


def backend_for(public_id: str) -> Optional[str]:
    """Return the real backend model name for ``public_id``, or None if
    the id is not registered. Returning None (not raising) lets the
    caller collapse the unknown id to the default tier silently."""
    if not public_id:
        return None
    return _mapping().get(public_id)


def default_public_id() -> str:
    """The public id used when the caller doesn't pick one."""
    return DEFAULT_PUBLIC_ID
