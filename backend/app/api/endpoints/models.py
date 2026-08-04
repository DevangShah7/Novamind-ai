"""
GET /api/v1/models — public, no-auth model listing for the chat UI.

The OpenAI-style ``/v1/models`` requires an API key. The in-app chat
picker needs a public, unauthenticated listing so the dropdown can
populate before login and on the marketing page. The two endpoints
return the same shape (`{data: [{id, source, ...}]}`) so the frontend
can share the response handler.

Lists only the public NovaMind ids registered in ``alias_config``.
The ``source`` field is always ``"novamind"`` so the picker never
hints at the underlying engine.
"""
from typing import List
from pydantic import BaseModel

from fastapi import APIRouter

from app.core import alias_config


router = APIRouter()


class ModelInfo(BaseModel):
    id: str
    source: str = "novamind"
    created: int | None = None


class ModelListResponse(BaseModel):
    data: List[ModelInfo]
    engines: dict  # single key, kept for backward-compat with the frontend picker


@router.get("/models", response_model=ModelListResponse)
def list_models():
    """Public list of models the chat UI can pick from.

    Returns the NovaMind public ids registered in ``alias_config``.
    The ``engines`` map is collapsed to ``{"novamind": "up"}`` to
    preserve the response shape the frontend already parses, but it
    no longer leaks ollama / neural health.
    """
    data: List[ModelInfo] = [
        ModelInfo(id=public_id)
        for public_id in alias_config.list_public_ids()
    ]
    return ModelListResponse(
        data=data,
        engines={"novamind": "up"},
    )
