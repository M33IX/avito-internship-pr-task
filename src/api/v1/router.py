from fastapi import APIRouter

from .pull_requests.routes import router as pr_router
from .teams.routes import router as teams_router
from .users.routes import router as users_router

api_v1_router = APIRouter(prefix="")

api_v1_router.include_router(teams_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(pr_router)
