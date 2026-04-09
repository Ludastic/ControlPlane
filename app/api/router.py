from fastapi import APIRouter

from app.api.agent.router import router as agent_router
from app.api.admin.router import router as admin_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(agent_router)
api_router.include_router(admin_router)
