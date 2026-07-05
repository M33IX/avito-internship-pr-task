from typing import Annotated

from fastapi import APIRouter, Query, status

from api.v1.dependencies import UsersServiceDep
from api.v1.errors import ErrorResponse
from api.v1.users.schemas import (
    GetReviewResponse,
    SetIsActiveRequest,
    SetIsActiveResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/getReview",
    summary="Получить PR'ы, где пользователь назначен ревьювером",
    response_model=GetReviewResponse,
    response_description="Список PR'ов пользователя",
    status_code=status.HTTP_200_OK,
)
async def get_review(
    user_id: Annotated[str, Query(description="Идентификатор пользователя")],
    service: UsersServiceDep,
) -> GetReviewResponse:
    return await service.get_user_prs(user_id)


@router.post(
    "/setIsActive",
    summary="Установить флаг активности пользователя",
    response_model=SetIsActiveResponse,
    response_description="Обновлённый пользователь",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Пользователь не найден",
        },
    },
)
async def set_is_active(
    request: SetIsActiveRequest,
    service: UsersServiceDep,
) -> SetIsActiveResponse:
    return await service.set_user_activity_status(request)
