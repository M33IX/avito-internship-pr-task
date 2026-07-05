import uvicorn
from fastapi import FastAPI

from api import api_router
from api.v1.errors import ApiError, api_error_handler

app = FastAPI(
    title="PR Reviewer Assignment Service",
    version="1.0.0",
    openapi_tags=[
        {"name": "Teams"},
        {"name": "Users"},
        {"name": "PullRequests"},
        {"name": "Health"},
    ],
)
app.include_router(api_router)
app.add_exception_handler(ApiError, api_error_handler)  # type:ignore

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
