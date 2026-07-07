import logging
from typing import Annotated

from fastapi import Depends

from core.interfaces.logger import ILogger
from infrastructure.in_memory import InMemoryStorage, InMemoryUnitOfWork
from infrastructure.logging import StdLoggerAdapter
from services.pull_requests import PRService
from services.teams import TeamsService
from services.users import UsersService

storage = InMemoryStorage()
logger = StdLoggerAdapter(logging.getLogger("pr_reviewer_assignment"))


def get_uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(storage)


def get_logger() -> ILogger:
    return logger


async def get_pr_service() -> PRService:
    return PRService(uow=get_uow(), logger=get_logger())


async def get_teams_service() -> TeamsService:
    return TeamsService(uow=get_uow(), logger=get_logger())


async def get_users_service() -> UsersService:
    return UsersService(uow=get_uow(), logger=get_logger())


PRServiceDep = Annotated[PRService, Depends(get_pr_service)]
TeamsServiceDep = Annotated[TeamsService, Depends(get_teams_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
