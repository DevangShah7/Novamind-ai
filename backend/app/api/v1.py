from fastapi import APIRouter
from app.api.endpoints import auth, chats, search, agents, image, memory, admin, api_key, voice, users_me, models, billing

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
api_router.include_router(users_me.router, prefix="/users", tags=["users"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])

# Developer-platform endpoints (also mounted at /v1/* in main.py with
# API-key auth). Re-mounting them here under /api/v1/* with JWT auth
# would require a JWT-or-key dependency, which doesn't exist today;
# the /v1/* surface is the single source of truth until then.
# from app.api.endpoints import webhooks, organizations
# api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
# api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])