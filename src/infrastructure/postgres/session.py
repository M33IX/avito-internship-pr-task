from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import Settings, get_settings
from infrastructure.postgres.models import Base


def get_database_url(settings: Settings | None = None) -> str:
    return (settings or get_settings()).database_url


def create_postgres_engine(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    echo: bool | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> AsyncEngine:
    settings = settings or get_settings()
    return create_async_engine(
        database_url or settings.database_url,
        echo=settings.database_echo if echo is None else echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size if pool_size is None else pool_size,
        max_overflow=(
            settings.database_max_overflow if max_overflow is None else max_overflow
        ),
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def iter_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
