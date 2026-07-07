from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from api.v1 import dependencies
from core.interfaces.logger import ILogger
from infrastructure.in_memory import InMemoryStorage, InMemoryUnitOfWork
from tests.factories import SpyLogger


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def spy_logger() -> SpyLogger:
    return SpyLogger()


@pytest.fixture
def memory_storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def memory_uow(memory_storage: InMemoryStorage) -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(memory_storage)


@pytest.fixture
async def api_client(
    memory_storage: InMemoryStorage,
    spy_logger: SpyLogger,
) -> AsyncIterator[httpx.AsyncClient]:
    from main import app

    async def override_get_uow() -> AsyncIterator[InMemoryUnitOfWork]:
        async with InMemoryUnitOfWork(memory_storage) as uow:
            yield uow

    def override_get_logger() -> ILogger:
        return spy_logger

    app.dependency_overrides[dependencies.get_uow] = override_get_uow
    app.dependency_overrides[dependencies.get_logger] = override_get_logger

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()
