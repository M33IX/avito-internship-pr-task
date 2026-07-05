from fastapi import APIRouter, status

from api.v1.dependencies import PRServiceDep
from api.v1.errors import ErrorCode, ErrorResponse
from api.v1.pull_requests.schemas import (
    CreatePrRequest,
    CreatePrResponse,
    MergePrRequest,
    MergePrResponse,
    ReassignPrRequest,
    ReassignPrResponse,
)

router = APIRouter(prefix="/pullRequest", tags=["PullRequests"])


@router.post(
    "/create",
    summary="Создать PR и автоматически назначить до 2 ревьюверов из команды автора",
    response_model=CreatePrResponse,
    response_description="PR создан",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Автор/команда не найдены",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "PR уже существует",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": ErrorCode.PR_EXISTS,
                            "message": "PR id already exists",
                        }
                    }
                }
            },
        },
    },
)
async def create_pr(
    request: CreatePrRequest,
    service: PRServiceDep,
) -> CreatePrResponse:
    return await service.create_pr(request)


@router.post(
    "/merge",
    summary="Пометить PR как MERGED (идемпотентная операция)",
    response_model=MergePrResponse,
    response_description="PR в состоянии MERGED",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "PR не найден",
        },
    },
)
async def merge_pr(
    request: MergePrRequest,
    service: PRServiceDep,
) -> MergePrResponse:
    return await service.merge_pr(request)


@router.post(
    "/reassign",
    summary="Переназначить конкретного ревьювера на другого из его команды",
    response_model=ReassignPrResponse,
    response_description="Переназначение выполнено",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "PR или пользователь не найден",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Нарушение доменных правил переназначения",
            "content": {
                "application/json": {
                    "examples": {
                        "merged": {
                            "summary": "Нельзя менять после MERGED",
                            "value": {
                                "error": {
                                    "code": ErrorCode.PR_MERGED,
                                    "message": "cannot reassign on merged PR",
                                }
                            },
                        },
                        "notAssigned": {
                            "summary": "Пользователь не был назначен ревьювером",
                            "value": {
                                "error": {
                                    "code": ErrorCode.NOT_ASSIGNED,
                                    "message": "reviewer is not assigned to this PR",
                                }
                            },
                        },
                        "noCandidate": {
                            "summary": "Нет доступных кандидатов",
                            "value": {
                                "error": {
                                    "code": ErrorCode.NO_CANDIDATE,
                                    "message": (
                                        "no active replacement candidate in team"
                                    ),
                                }
                            },
                        },
                    }
                }
            },
        },
    },
)
async def reassign_reviewer(
    request: ReassignPrRequest,
    service: PRServiceDep,
) -> ReassignPrResponse:
    return await service.reassign_reviewer(request)
