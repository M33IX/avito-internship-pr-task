from core.application.use_cases import get_service_stats
from core.domain.entities import ServiceStats
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


class HealthService:
    def __init__(
        self,
        uow: IUnitOfWork,
        logger: ILogger,
    ) -> None:
        self._uow = uow
        self._logger = logger

    async def check_database(self) -> None:
        await self._uow.teams.count()
        self._logger.info("health check completed", database="ok")

    async def get_stats(self) -> ServiceStats:
        return await get_service_stats(uow=self._uow, logger=self._logger)
