from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from core.exceptions import (
    AppError,
    NoReviewerCandidateError,
    PullRequestAlreadyExistsError,
    PullRequestMergedError,
    PullRequestNotFoundError,
    ReviewerNotAssignedError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
    UserNotFoundError,
)


class ErrorCode(StrEnum):
    TEAM_EXISTS = "TEAM_EXISTS"
    PR_EXISTS = "PR_EXISTS"
    PR_MERGED = "PR_MERGED"
    NOT_ASSIGNED = "NOT_ASSIGNED"
    NO_CANDIDATE = "NO_CANDIDATE"
    NOT_FOUND = "NOT_FOUND"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": ErrorCode.NOT_FOUND,
                    "message": "resource not found",
                }
            }
        }
    )


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


DOMAIN_ERROR_MAPPING: dict[type[AppError], tuple[int, ErrorCode]] = {
    TeamAlreadyExistsError: (400, ErrorCode.TEAM_EXISTS),
    TeamNotFoundError: (404, ErrorCode.NOT_FOUND),
    UserNotFoundError: (404, ErrorCode.NOT_FOUND),
    PullRequestAlreadyExistsError: (409, ErrorCode.PR_EXISTS),
    PullRequestNotFoundError: (404, ErrorCode.NOT_FOUND),
    PullRequestMergedError: (409, ErrorCode.PR_MERGED),
    ReviewerNotAssignedError: (409, ErrorCode.NOT_ASSIGNED),
    NoReviewerCandidateError: (409, ErrorCode.NO_CANDIDATE),
}


def build_error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    status_code, code = DOMAIN_ERROR_MAPPING[type(exc)]
    return build_error_response(
        status_code=status_code,
        code=code,
        message=exc.message,
    )
