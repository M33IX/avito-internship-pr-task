from typing import Annotated

from fastapi import Depends

from services.pull_requests import PRService
from services.teams import TeamsService
from services.users import UsersService


async def get_pr_service() -> PRService:
    return PRService()


async def get_teams_service() -> TeamsService:
    return TeamsService()


async def get_users_service() -> UsersService:
    return UsersService()


PRServiceDep = Annotated[PRService, Depends(get_pr_service)]
TeamsServiceDep = Annotated[TeamsService, Depends(get_teams_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
