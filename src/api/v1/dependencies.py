import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from config import Settings, get_settings
from core.interfaces.logger import ILogger
from infrastructure.logging import StdLoggerAdapter
from infrastructure.metrics import register_engine_metrics
from infrastructure.postgres import (
    PostgresUnitOfWork,
    create_postgres_engine,
    create_session_factory,
    iter_uow,
)
from services.health import HealthService
from services.pull_requests import PRService
from services.teams import TeamsService
from services.users import UsersService

logger = StdLoggerAdapter(logging.getLogger("pr_reviewer_assignment"))
engine = create_postgres_engine()
register_engine_metrics(engine)
session_factory = create_session_factory(engine)


def get_app_settings() -> Settings:
    return get_settings()


async def get_uow() -> AsyncIterator[PostgresUnitOfWork]:
    async for uow in iter_uow(session_factory):
        yield uow


def get_logger() -> ILogger:
    return logger


UowDep = Annotated[PostgresUnitOfWork, Depends(get_uow)]
LoggerDep = Annotated[ILogger, Depends(get_logger)]


async def get_pr_service(uow: UowDep, logger: LoggerDep) -> PRService:
    return PRService(uow=uow, logger=logger)


async def get_teams_service(uow: UowDep, logger: LoggerDep) -> TeamsService:
    return TeamsService(uow=uow, logger=logger)


async def get_users_service(uow: UowDep, logger: LoggerDep) -> UsersService:
    return UsersService(uow=uow, logger=logger)


async def get_health_service(uow: UowDep, logger: LoggerDep) -> HealthService:
    return HealthService(uow=uow, logger=logger)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
PRServiceDep = Annotated[PRService, Depends(get_pr_service)]
TeamsServiceDep = Annotated[TeamsService, Depends(get_teams_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
