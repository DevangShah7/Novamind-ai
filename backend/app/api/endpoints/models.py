"""
GET /api/v1/models — public, no-auth model listing for the chat UI.

The OpenAI-style ``/v1/models`` requires an API key. The in-app chat
picker needs a public, unauthenticated listing so the dropdown can
populate before login and on the marketing page. The two endpoints
return the same shape (`{data: [{id, source, ...}]}`) so the frontend
can share the response handler.

Stealth surface: only NovaMind public ids are ever listed. The real
backend (Ollama, a local model, a hosted API) is read from
``alias_config``. The ``engines`` map carries a single ``novamind``
flag so the UI doesn't need to know which engine is underneath.
"""

from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter

from app.core import alias_config


router = APIRouter()


class ModelInfo(BaseModel):
    id: str
    source: str  # always "novamind" on the public surface
    created: Optional[int] = None


class ModelListResponse(BaseModel):
    data: List[ModelInfo]
    engines: dict  # {"novamind": "up"} — the brand is always up by definition


@router.get("/models", response_model=ModelListResponse)
def list_models():
    """Public list of models the chat UI can pick from.

    Returns only the public NovaMind ids registered in
    ``alias_config``. Order is stable (default tier first, then the
    rest alphabetical) so the dropdown never reshuffles.
    """
    data: List[ModelInfo] = [
        ModelInfo(id=public_id, source="novamind") for public_id in alias_config.list_public_ids()
    ]
    return ModelListResponse(
        data=data,
        engines={"novamind": "up"},
    )
