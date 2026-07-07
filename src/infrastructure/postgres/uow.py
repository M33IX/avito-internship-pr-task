from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.interfaces.uow import IUnitOfWork
from infrastructure.postgres.repositories import (
    PostgresPullRequestReviewersRepository,
    PostgresPullRequestsRepository,
    PostgresTeamsRepository,
    PostgresUsersRepository,
)


class PostgresUnitOfWork(IUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.teams = PostgresTeamsRepository(session)
        self.users = PostgresUsersRepository(session)
        self.pull_requests = PostgresPullRequestsRepository(session)
        self.pull_request_reviewers = PostgresPullRequestReviewersRepository(session)

    async def __aenter__(self) -> PostgresUnitOfWork:
        if not self._session.in_transaction():
            await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc is not None:
            await self.rollback()
            return

        await self.commit()

    async def commit(self) -> None:
        if self._session.in_transaction():
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session.in_transaction():
            await self._session.rollback()


async def iter_uow(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[PostgresUnitOfWork]:
    async with session_factory() as session, PostgresUnitOfWork(session) as uow:
        yield uow
