from typing import Annotated

from fastapi import APIRouter, Query, status

from api.v1.dependencies import TeamsServiceDep
from api.v1.errors import ErrorCode, ErrorResponse
from api.v1.teams.schemas import (
    CreateTeamResponse,
    DeactivateTeamRequest,
    DeactivateTeamResponse,
    Team,
)
from api.v1.validation import TeamName

router = APIRouter(prefix="/team", tags=["Teams"])


@router.get(
    "/get",
    summary="Получить команду с участниками",
    response_model=Team,
    response_description="Объект команды",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Команда не найдена",
        },
    },
)
async def team_get(
    team_name: Annotated[TeamName, Query(description="Уникальное имя команды")],
    service: TeamsServiceDep,
) -> Team:
    return await service.get_team(team_name)


@router.post(
    "/add",
    summary="Создать команду с участниками (создаёт/обновляет пользователей)",
    response_model=CreateTeamResponse,
    response_description="Команда создана",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Команда уже существует",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": ErrorCode.TEAM_EXISTS,
                            "message": "team_name already exists",
                        }
                    }
                }
            },
        },
    },
)
async def add_team(
    team: Team,
    service: TeamsServiceDep,
) -> CreateTeamResponse:
    return await service.add_team(team)


@router.post(
    "/deactivate",
    summary="Деактивировать команду с безопасным переназначением открытых PR",
    response_model=DeactivateTeamResponse,
    response_description="Команда деактивирована, открытые PR переназначены",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Команда или команда для переназначения не найдена",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Не удалось безопасно переназначить все открытые PR",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": ErrorCode.NO_CANDIDATE,
                            "message": "no active replacement candidate in team",
                        }
                    }
                }
            },
        },
    },
)
async def deactivate_team(
    request: DeactivateTeamRequest,
    service: TeamsServiceDep,
) -> DeactivateTeamResponse:
    return await service.deactivate_team(request)
