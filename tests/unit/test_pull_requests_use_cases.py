from __future__ import annotations

import pytest

from core.application.use_cases import (
    AddTeamCommand,
    CreatePullRequestCommand,
    MergePullRequestCommand,
    ReassignPullRequestReviewerCommand,
    TeamMemberInput,
    add_team,
    create_pull_request,
    merge_pull_request,
    reassign_pull_request_reviewer,
)
from core.domain.entities import TeamMember
from core.domain.enums.pull_requests import PRStatus
from core.exceptions import (
    NoReviewerCandidateError,
    PullRequestAlreadyExistsError,
    PullRequestMergedError,
    PullRequestNotFoundError,
    ReviewerNotAssignedError,
    UserNotFoundError,
)
from infrastructure.in_memory import InMemoryUnitOfWork
from tests.factories import SpyLogger, backend_team_command

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def deterministic_random(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.application.use_cases.pull_requests.random.sample",
        lambda population, k: list(population)[:k],
    )
    monkeypatch.setattr(
        "core.application.use_cases.pull_requests.random.choice",
        lambda population: list(population)[0],
    )


async def _add_backend_team(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=backend_team_command(),
        uow=memory_uow,
        logger=spy_logger,
    )


async def _create_backend_pr(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
    pull_request_id: str = "pr1",
) -> None:
    await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id=pull_request_id,
            pull_request_name="Add search",
            author_id="u1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )


@pytest.mark.anyio
async def test_create_pull_request_assigns_two_active_reviewers(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)

    pull_request = await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id="pr1",
            pull_request_name="Add search",
            author_id="u1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert pull_request.status == PRStatus.OPEN
    assert pull_request.assigned_reviewers == ["u2", "u3"]
    assert "u1" not in pull_request.assigned_reviewers
    assert "u5" not in pull_request.assigned_reviewers


@pytest.mark.anyio
async def test_create_pull_request_assigns_one_reviewer_when_only_one_available(
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

    pull_request = await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id="pr1",
            pull_request_name="Pair PR",
            author_id="a1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert pull_request.assigned_reviewers == ["r1"]


@pytest.mark.anyio
async def test_create_pull_request_assigns_no_reviewers_when_none_available(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await add_team(
        command=AddTeamCommand(
            team_name="solo",
            members=[
                TeamMemberInput(user_id="a1", username="Author", is_active=True),
            ],
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    pull_request = await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id="pr1",
            pull_request_name="Solo PR",
            author_id="a1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert pull_request.assigned_reviewers == []


@pytest.mark.anyio
async def test_create_pull_request_rejects_duplicate_pr(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)

    with pytest.raises(PullRequestAlreadyExistsError, match="PR id already exists"):
        await _create_backend_pr(memory_uow, spy_logger)


@pytest.mark.anyio
async def test_create_pull_request_raises_when_author_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    with pytest.raises(UserNotFoundError, match="resource not found"):
        await create_pull_request(
            command=CreatePullRequestCommand(
                pull_request_id="pr1",
                pull_request_name="Missing author",
                author_id="missing",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_merge_pull_request_is_idempotent(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)

    first = await merge_pull_request(
        command=MergePullRequestCommand(pull_request_id="pr1"),
        uow=memory_uow,
        logger=spy_logger,
    )
    second = await merge_pull_request(
        command=MergePullRequestCommand(pull_request_id="pr1"),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert first.status == PRStatus.MERGED
    assert second.status == PRStatus.MERGED
    assert first.merged_at == second.merged_at


@pytest.mark.anyio
async def test_merge_pull_request_raises_when_pr_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    with pytest.raises(PullRequestNotFoundError, match="resource not found"):
        await merge_pull_request(
            command=MergePullRequestCommand(pull_request_id="missing"),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_replaces_old_reviewer(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)

    result = await reassign_pull_request_reviewer(
        command=ReassignPullRequestReviewerCommand(
            pull_request_id="pr1",
            old_user_id="u2",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert result.replaced_by == "u4"
    assert result.pull_request.assigned_reviewers == ["u4", "u3"]


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_raises_when_pr_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    with pytest.raises(PullRequestNotFoundError, match="resource not found"):
        await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id="missing",
                old_user_id="u2",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_raises_when_old_reviewer_is_missing(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)

    with pytest.raises(UserNotFoundError, match="resource not found"):
        await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id="pr1",
                old_user_id="missing",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_rejects_merged_pr(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)
    await merge_pull_request(
        command=MergePullRequestCommand(pull_request_id="pr1"),
        uow=memory_uow,
        logger=spy_logger,
    )

    with pytest.raises(PullRequestMergedError, match="cannot reassign on merged PR"):
        await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id="pr1",
                old_user_id="u2",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_rejects_not_assigned_user(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await _add_backend_team(memory_uow, spy_logger)
    await _create_backend_pr(memory_uow, spy_logger)

    with pytest.raises(
        ReviewerNotAssignedError,
        match="reviewer is not assigned to this PR",
    ):
        await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id="pr1",
                old_user_id="u4",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_pull_request_reviewer_raises_when_no_candidate_exists(
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
    await create_pull_request(
        command=CreatePullRequestCommand(
            pull_request_id="pr1",
            pull_request_name="Pair PR",
            author_id="a1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    with pytest.raises(
        NoReviewerCandidateError,
        match="no active replacement candidate in team",
    ):
        await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id="pr1",
                old_user_id="r1",
            ),
            uow=memory_uow,
            logger=spy_logger,
        )


@pytest.mark.anyio
async def test_reassign_uses_old_reviewers_team_for_replacement(
    memory_uow: InMemoryUnitOfWork,
    spy_logger: SpyLogger,
) -> None:
    await memory_uow.teams.create("authors")
    await memory_uow.users.upsert_many(
        team_name="authors",
        users=[TeamMember(user_id="a1", username="Author", is_active=True)],
    )
    await memory_uow.teams.create("reviewers")
    await memory_uow.users.upsert_many(
        team_name="reviewers",
        users=[
            TeamMember(user_id="r1", username="Old", is_active=True),
            TeamMember(user_id="r2", username="New", is_active=True),
        ],
    )
    await memory_uow.pull_requests.create(
        pull_request_id="pr1",
        pull_request_name="Cross team",
        author_id="a1",
    )
    await memory_uow.pull_request_reviewers.add_reviewers(
        pull_request_id="pr1",
        reviewer_ids=["r1"],
    )

    result = await reassign_pull_request_reviewer(
        command=ReassignPullRequestReviewerCommand(
            pull_request_id="pr1",
            old_user_id="r1",
        ),
        uow=memory_uow,
        logger=spy_logger,
    )

    assert result.replaced_by == "r2"
    assert result.pull_request.assigned_reviewers == ["r2"]
