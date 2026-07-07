from __future__ import annotations

import pytest

from core.application.use_cases import (
    AddTeamCommand,
    TeamMemberInput,
    add_team,
    get_team,
)
from core.exceptions import TeamAlreadyExistsError, TeamNotFoundError
from infrastructure.in_memory import InMemoryUnitOfWork
from tests.factories import SpyLogger, backend_team_command

pytestmark = pytest.mark.unit


@pytest.mark.anyio
async def test_add_team_creates_team_and_users(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    team = await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert team.team_name == "backend"
    assert [member.user_id for member in team.members] == [
        "u1",
        "u2",
        "u3",
        "u4",
        "u5",
    ]
    assert team.members[-1].is_active is False
    assert spy_logger.records[-1].message == "team created"


@pytest.mark.anyio
async def test_add_team_rejects_duplicate_team(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    command = backend_team_command()
    await add_team(command=command, uow=memory_uow, logger=spy_logger)

    with pytest.raises(TeamAlreadyExistsError, match="team_name already exists"):
        await add_team(command=command, uow=memory_uow, logger=spy_logger)


@pytest.mark.anyio
async def test_get_team_returns_existing_team(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=AddTeamCommand(
            team_name="pair",
            members=[
                TeamMemberInput(user_id="a1", username="Author", is_active=True),
                TeamMemberInput(user_id="r1", username="Reviewer", is_active=True),
            ],
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    team = await get_team("pair", uow=memory_uow, logger=spy_logger)

    assert team.team_name == "pair"
    assert [member.user_id for member in team.members] == ["a1", "r1"]


@pytest.mark.anyio
async def test_get_team_raises_when_team_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    with pytest.raises(TeamNotFoundError, match="resource not found"):
        await get_team("missing", uow=memory_uow, logger=spy_logger)
