from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from core.domain.entities import TeamMember
from core.domain.enums.pull_requests import PRStatus
from infrastructure.postgres.models import PullRequestReviewerModel
from infrastructure.postgres.repositories import (
    PostgresPullRequestReviewersRepository,
    PostgresPullRequestsRepository,
    PostgresTeamsRepository,
    PostgresUsersRepository,
)
from infrastructure.postgres.uow import PostgresUnitOfWork
from tests.factories import domain_team_members

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def seed_backend(session: AsyncSession) -> None:
    teams = PostgresTeamsRepository(session)
    users = PostgresUsersRepository(session)

    await teams.create("backend")
    await users.upsert_many("backend", domain_team_members())
    await session.commit()


async def seed_pull_request(
    session: AsyncSession,
    *,
    pull_request_id: str = "pr1",
    reviewer_ids: list[str] | None = None,
) -> None:
    await seed_backend(session)
    pull_requests = PostgresPullRequestsRepository(session)
    reviewers = PostgresPullRequestReviewersRepository(session)

    await pull_requests.create(
        pull_request_id=pull_request_id,
        pull_request_name=f"PR {pull_request_id}",
        author_id="u1",
    )
    await reviewers.add_reviewers(
        pull_request_id=pull_request_id,
        reviewer_ids=reviewer_ids or ["u2", "u3"],
    )
    await session.commit()


async def test_alembic_migrates_schema(postgres_engine: AsyncEngine) -> None:
    async with postgres_engine.connect() as connection:
        version = await connection.scalar(text("select version()"))
        alembic_version = await connection.scalar(
            text("select version_num from alembic_version")
        )
        rows = (
            await connection.execute(
                text(
                    """
                    select table_name, column_name, character_maximum_length
                    from information_schema.columns
                    where table_name in ('teams', 'users')
                    and column_name = 'team_name'
                    """
                )
            )
        ).all()

    lengths = {
        (row.table_name, row.column_name): row.character_maximum_length for row in rows
    }
    assert version is not None
    assert "PostgreSQL 18" in version
    assert alembic_version == "0001_initial_schema"
    assert lengths == {
        ("teams", "team_name"): 100,
        ("users", "team_name"): 100,
    }


async def test_teams_repository_create_exists_and_get_by_name(
    postgres_session: AsyncSession,
) -> None:
    teams = PostgresTeamsRepository(postgres_session)
    users = PostgresUsersRepository(postgres_session)

    assert await teams.exists("empty") is False
    await teams.create("empty")
    assert await teams.exists("empty") is True
    empty_team = await teams.get_by_name("empty")
    assert empty_team is not None
    assert empty_team.members == []

    await teams.create("backend")
    await users.upsert_many(
        "backend",
        [
            TeamMember(user_id="u3", username="Three", is_active=True),
            TeamMember(user_id="u1", username="One", is_active=True),
            TeamMember(user_id="u2", username="Two", is_active=False),
        ],
    )

    team = await teams.get_by_name("backend")

    assert team is not None
    assert team.team_name == "backend"
    assert [member.user_id for member in team.members] == ["u1", "u2", "u3"]
    assert [member.is_active for member in team.members] == [True, False, True]


async def test_users_repository_upsert_update_move_and_list_active(
    postgres_session: AsyncSession,
) -> None:
    teams = PostgresTeamsRepository(postgres_session)
    users = PostgresUsersRepository(postgres_session)
    await teams.create("backend")
    await teams.create("platform")

    await users.upsert_many(
        "backend",
        [
            TeamMember(user_id="u1", username="One", is_active=True),
            TeamMember(user_id="u2", username="Two", is_active=True),
            TeamMember(user_id="u3", username="Three", is_active=True),
        ],
    )
    await users.upsert_many(
        "platform",
        [TeamMember(user_id="u2", username="Moved", is_active=False)],
    )

    moved_user = await users.get_by_id("u2")
    assert moved_user is not None
    assert moved_user.username == "Moved"
    assert moved_user.team_name == "platform"
    assert moved_user.is_active is False

    activated_user = await users.set_active("u2", True)
    assert activated_user is not None
    assert activated_user.is_active is True

    active_backend_users = await users.list_active_by_team(
        "backend",
        exclude_user_ids={"u1"},
        limit=1,
    )
    active_platform_users = await users.list_active_by_team("platform")

    assert [user.user_id for user in active_backend_users] == ["u3"]
    assert [user.user_id for user in active_platform_users] == ["u2"]


async def test_pull_requests_repository_crud_merge_and_list_by_reviewer(
    postgres_session: AsyncSession,
) -> None:
    await seed_pull_request(
        postgres_session,
        reviewer_ids=["u3", "u2"],
    )
    pull_requests = PostgresPullRequestsRepository(postgres_session)

    pull_request = await pull_requests.get_by_id("pr1")
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["u3", "u2"]

    merged = await pull_requests.mark_merged("pr1")
    assert merged is not None
    assert merged.status == PRStatus.MERGED
    assert merged.merged_at is not None

    merged_again = await pull_requests.mark_merged("pr1")
    assert merged_again is not None
    assert merged_again.merged_at == merged.merged_at

    reviewer_prs = await pull_requests.list_by_reviewer("u2")
    assert [pr.pull_request_id for pr in reviewer_prs] == ["pr1"]


async def test_reviewers_repository_add_is_assigned_and_replace_preserves_slot(
    postgres_session: AsyncSession,
) -> None:
    await seed_pull_request(postgres_session, reviewer_ids=["u2", "u3"])
    pull_requests = PostgresPullRequestsRepository(postgres_session)
    reviewers = PostgresPullRequestReviewersRepository(postgres_session)

    assert await reviewers.is_assigned("pr1", "u2") is True
    assert await reviewers.is_assigned("pr1", "u4") is False

    await reviewers.replace_reviewer(
        pull_request_id="pr1",
        old_user_id="u2",
        new_user_id="u4",
    )

    pull_request = await pull_requests.get_by_id("pr1")
    replacement_slot = await postgres_session.scalar(
        select(PullRequestReviewerModel.slot).where(
            PullRequestReviewerModel.pull_request_id == "pr1",
            PullRequestReviewerModel.reviewer_id == "u4",
        )
    )
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["u4", "u3"]
    assert replacement_slot == 1


async def test_uow_commits_successful_context(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with (
        postgres_session_factory() as session,
        PostgresUnitOfWork(session) as uow,
    ):
        await uow.teams.create("committed")

    async with postgres_session_factory() as session:
        assert await PostgresTeamsRepository(session).exists("committed") is True


async def test_uow_rolls_back_failed_context(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class ExpectedError(Exception): ...

    with pytest.raises(ExpectedError):
        async with (
            postgres_session_factory() as session,
            PostgresUnitOfWork(session) as uow,
        ):
            await uow.teams.create("rolled_back")
            raise ExpectedError

    async with postgres_session_factory() as session:
        assert await PostgresTeamsRepository(session).exists("rolled_back") is False


async def test_repository_queries_do_not_have_n_plus_one(
    postgres_session: AsyncSession,
    statement_counter: Callable[[], Any],
) -> None:
    await seed_pull_request(postgres_session, pull_request_id="pr1")
    pull_requests = PostgresPullRequestsRepository(postgres_session)
    reviewers = PostgresPullRequestReviewersRepository(postgres_session)
    await pull_requests.create(
        pull_request_id="pr2",
        pull_request_name="PR pr2",
        author_id="u1",
    )
    await reviewers.add_reviewers(pull_request_id="pr2", reviewer_ids=["u2", "u3"])
    await postgres_session.commit()

    teams = PostgresTeamsRepository(postgres_session)

    with statement_counter() as counter:
        team = await teams.get_by_name("backend")
    assert team is not None
    assert len(team.members) == 5
    assert counter.count == 1

    with statement_counter() as counter:
        pull_request = await pull_requests.get_by_id("pr1")
    assert pull_request is not None
    assert pull_request.assigned_reviewers == ["u2", "u3"]
    assert counter.count == 1

    with statement_counter() as counter:
        reviewer_prs = await pull_requests.list_by_reviewer("u2")
    assert [pr.pull_request_id for pr in reviewer_prs] == ["pr1", "pr2"]
    assert counter.count == 1
