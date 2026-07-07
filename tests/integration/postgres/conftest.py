from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from config import get_settings
from infrastructure.postgres import create_postgres_engine, create_session_factory

pytest.importorskip("testcontainers.postgres")
from testcontainers.postgres import PostgresContainer  # noqa: E402

ROOT_PATH = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class StatementCounter:
    engine: AsyncEngine
    count: int = 0

    def _before_cursor_execute(self, *_args: Any, **_kwargs: Any) -> None:
        self.count += 1

    def __enter__(self) -> StatementCounter:
        event.listen(
            self.engine.sync_engine,
            "before_cursor_execute",
            self._before_cursor_execute,
        )
        return self

    def __exit__(self, *_args: Any) -> None:
        event.remove(
            self.engine.sync_engine,
            "before_cursor_execute",
            self._before_cursor_execute,
        )


@pytest.fixture(scope="session")
def postgres_database_url() -> Iterator[str]:
    old_database_url = os.environ.get("DATABASE_URL")

    with PostgresContainer("postgres:18", driver="asyncpg") as postgres:
        database_url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = database_url
        get_settings.cache_clear()

        alembic_config = Config(str(ROOT_PATH / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        yield database_url

    if old_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old_database_url
    get_settings.cache_clear()


@pytest.fixture
async def postgres_engine(
    postgres_database_url: str,
) -> AsyncIterator[AsyncEngine]:
    engine = create_postgres_engine(
        database_url=postgres_database_url,
        pool_size=1,
        max_overflow=0,
    )
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE pull_request_reviewers, pull_requests, users, teams "
                "RESTART IDENTITY CASCADE"
            )
        )

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def postgres_session_factory(
    postgres_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield create_session_factory(postgres_engine)


@pytest.fixture
async def postgres_session(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with postgres_session_factory() as session:
        yield session


@pytest.fixture
def statement_counter(postgres_engine: AsyncEngine):
    def create_counter() -> StatementCounter:
        return StatementCounter(postgres_engine)

    return create_counter
