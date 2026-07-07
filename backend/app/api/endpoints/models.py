"""
GET /api/v1/models — public, no-auth model listing for the chat UI.

The OpenAI-style ``/v1/models`` requires an API key. The in-app chat
picker needs a public, unauthenticated listing so the dropdown can
populate before login and on the marketing page. The two endpoints
return the same shape (`{data: [{id, source, ...}]}`) so the frontend
can share the response handler.

The local engine is always listed. Ollama models are appended when
Ollama is reachable; otherwise the response carries `engines.ollama =
"down"` so the UI can show a warning.
"""
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter

from app.core.ollama_service import ollama_list_models, ollama_reachable


router = APIRouter()


class ModelInfo(BaseModel):
    id: str
    source: str  # "local" or "ollama"
    created: Optional[int] = None


class ModelListResponse(BaseModel):
    data: List[ModelInfo]
    engines: dict  # {ollama: "up"|"down", local: "up"}


@router.get("/models", response_model=ModelListResponse)
def list_models():
    """Public list of models the chat UI can pick from.

    Always includes ``NovaMind-local-v1`` (the in-process rule engine).
    Adds any Ollama models that are currently installed when Ollama is
    reachable. The ``engines`` map lets the UI show engine health in
    the picker.
    """
    data: List[ModelInfo] = [
        ModelInfo(id="NovaMind-local-v1", source="local"),
    ]
    ollama_up = ollama_reachable()
    if ollama_up:
        for m in ollama_list_models():
            data.append(
                ModelInfo(
                    id=m["id"],
                    source="ollama",
                    created=m.get("created"),
                )
            )
    return ModelListResponse(
        data=data,
        engines={
            "ollama": "up" if ollama_up else "down",
            "local": "up",
        },
    )
