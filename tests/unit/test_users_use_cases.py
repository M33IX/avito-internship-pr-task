from __future__ import annotations

import pytest

from core.application.use_cases import (
    CreatePullRequestCommand,
    SetUserActivityCommand,
    add_team,
    create_pull_request,
    get_user_review_pull_requests,
    set_user_activity,
)
from core.exceptions import UserNotFoundError
from infrastructure.in_memory import InMemoryUnitOfWork
from tests.factories import SpyLogger, backend_team_command

pytestmark = pytest.mark.unit


@pytest.mark.anyio
async def test_set_user_activity_updates_user(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )

    user = await set_user_activity(
        command=SetUserActivityCommand(user_id="u2", is_active=False),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert user.user_id == "u2"
    assert user.is_active is False


@pytest.mark.anyio
async def test_set_user_activity_raises_when_user_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    with pytest.raises(UserNotFoundError, match="resource not found"):
        await set_user_activity(
            command=SetUserActivityCommand(user_id="missing", is_active=False),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_get_user_review_pull_requests_returns_short_prs(
    monkeypatch: pytest.MonkeyPatch,
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    monkeypatch.setattr(
        "core.application.use_cases.pull_requests.random.sample",
        lambda population, k: list(population)[:k],
    )
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )
    await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id="pr1",
            pull_request_name="Add search",
            author_id="u1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    pull_requests = await get_user_review_pull_requests(
        user_id="u2",
        uow=memory_uow,
        logger=spy_logger,
    )

    assert len(pull_requests) == 1
    assert pull_requests[0].pull_request_id == "pr1"
    assert pull_requests[0].pull_request_name == "Add search"
