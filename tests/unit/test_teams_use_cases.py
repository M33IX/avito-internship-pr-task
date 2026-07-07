from __future__ import annotations

import pytest

from core.application.use_cases import (
    AddTeamCommand,
    DeactivateTeamCommand,
    TeamMemberInput,
    add_team,
    deactivate_team,
    get_team,
)
from core.domain.enums.pull_requests import PRStatus
from core.exceptions import (
    NoReviewerCandidateError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
)
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


async def _add_platform_team(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
    *,
    members_count: int = 2,
) -> None:
    await add_team(
        command=AddTeamCommand(
            team_name="platform",
            members=[
                TeamMemberInput(
                    user_id=f"p{index}",
                    username=f"Platform {index}",
                    is_active=True,
                )
                for index in range(1, members_count + 1)
            ],
        ),
        uow=memory_uow,
        logger=spy_logger,
    )


async def _add_backend_pull_request(
    memory_uow: InMemoryUnitOfWork,
    *,
    status: PRStatus = PRStatus.OPEN,
) -> None:
    await memory_uow.pull_requests.create(
        pull_request_id="pr1",
        pull_request_name="Add search",
        author_id="u1",
    )
    await memory_uow.pull_request_reviewers.add_reviewers(
        pull_request_id="pr1",
        reviewer_ids=["u2", "u3"],
    )
    if status == PRStatus.MERGED:
        await memory_uow.pull_requests.mark_merged("pr1")


@pytest.mark.anyio
async def test_deactivate_team_reassigns_open_prs_to_replacement_team(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )
    await _add_platform_team(memory_uow, spy_logger)
    await _add_backend_pull_request(memory_uow)

    result = await deactivate_team(
        command=DeactivateTeamCommand(
            team_name="backend",
            replacement_team_name="platform",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert [member.is_active for member in result.team.members] == [
        False,
        False,
        False,
        False,
        False,
    ]
    assert [
        (
            reassignment.pull_request_id,
            reassignment.old_user_id,
            reassignment.new_user_id,
        )
        for reassignment in result.reassignments
    ] == [("pr1", "u2", "p1"), ("pr1", "u3", "p2")]

    pull_request = await memory_uow.pull_requests.get_by_id("pr1")
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["p1", "p2"]


@pytest.mark.anyio
async def test_deactivate_team_rejects_when_not_all_prs_can_be_reassigned(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )
    await _add_platform_team(memory_uow, spy_logger, members_count=1)
    await _add_backend_pull_request(memory_uow)

    with pytest.raises(
        NoReviewerCandidateError,
        match="no active replacement candidate in team",
    ):
        await deactivate_team(
            command=DeactivateTeamCommand(
                team_name="backend",
                replacement_team_name="platform",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )

    team = await memory_uow.teams.get_by_name("backend")
    pull_request = await memory_uow.pull_requests.get_by_id("pr1")
    assert team is not None
    assert [member.is_active for member in team.members] == [
        True,
        True,
        True,
        True,
        False,
    ]
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["u2", "u3"]


@pytest.mark.anyio
async def test_deactivate_team_does_not_reassign_merged_pull_requests(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )
    await _add_platform_team(memory_uow, spy_logger, members_count=0)
    await _add_backend_pull_request(memory_uow, status=PRStatus.MERGED)

    result = await deactivate_team(
        command=DeactivateTeamCommand(
            team_name="backend",
            replacement_team_name="platform",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    pull_request = await memory_uow.pull_requests.get_by_id("pr1")
    assert result.reassignments == []
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["u2", "u3"]
    assert all(not member.is_active for member in result.team.members)


@pytest.mark.anyio
async def test_deactivate_team_raises_when_replacement_team_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )

    with pytest.raises(TeamNotFoundError, match="resource not found"):
        await deactivate_team(
            command=DeactivateTeamCommand(
                team_name="backend",
                replacement_team_name="missing",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )
