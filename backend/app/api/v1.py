from fastapi import APIRouter
from app.api.endpoints import auth, chats, search, agents, image, memory, admin, api_key, voice

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(image.router, prefix="/image", tags=["image"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(api_key.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])