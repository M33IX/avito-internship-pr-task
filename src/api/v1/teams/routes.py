from typing import Annotated

from fastapi import APIRouter, Query, status

from api.v1.errors import ErrorCode, ErrorResponse
from api.v1.teams.schemas import CreateTeamResponse, Team

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
    team_name: Annotated[str, Query(description="Уникальное имя команды")],
) -> Team: ...


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
async def add_team(team: Team) -> CreateTeamResponse: ...
