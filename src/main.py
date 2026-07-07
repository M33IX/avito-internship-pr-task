import uvicorn
from fastapi import FastAPI

from api import api_router
from api.v1.errors import ApiError, api_error_handler, app_error_handler
from config import get_settings
from core.exceptions import AppError
from infrastructure.metrics import PrometheusMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    openapi_tags=[
        {"name": "Teams"},
        {"name": "Users"},
        {"name": "PullRequests"},
        {"name": "Health"},
    ],
)
app.add_middleware(PrometheusMiddleware)
app.include_router(api_router)
app.add_exception_handler(ApiError, api_error_handler)  # type:ignore
app.add_exception_handler(AppError, app_error_handler)  # type:ignore

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
