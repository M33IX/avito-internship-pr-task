from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.domain.entities import (
    PullRequest,
    PullRequestReviewer,
    PullRequestShort,
    Team,
    TeamMember,
    User,
)
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.repositories import (
    IPullRequestReviewersRepository,
    IPullRequestsRepository,
    ITeamsRepository,
    IUsersRepository,
)
from core.interfaces.uow import IUnitOfWork


@dataclass(slots=True)
class InMemoryStorage:
    teams: dict[str, Team] = field(default_factory=dict[str, Team])
    users: dict[str, User] = field(default_factory=dict[str, User])
    pull_requests: dict[str, PullRequest] = field(
        default_factory=dict[str, PullRequest]
    )
    reviewers: dict[str, list[PullRequestReviewer]] = field(
        default_factory=dict[str, list[PullRequestReviewer]]
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InMemoryTeamsRepository(ITeamsRepository):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage

    async def exists(self, team_name: str) -> bool:
        return team_name in self._storage.teams

    async def get_by_name(self, team_name: str) -> Team | None:
        if team_name not in self._storage.teams:
            return None

        members = [
            TeamMember(
                user_id=user.user_id,
                username=user.username,
                is_active=user.is_active,
            )
            for user in self._storage.users.values()
            if user.team_name == team_name
        ]
        members.sort(key=lambda member: member.user_id)
        return Team(team_name=team_name, members=members)

    async def create(self, team_name: str) -> None:
        self._storage.teams[team_name] = Team(team_name=team_name)


class InMemoryUsersRepository(IUsersRepository):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage

    async def get_by_id(self, user_id: str) -> User | None:
        return self._storage.users.get(user_id)

    async def upsert_many(
        self,
        team_name: str,
        users: list[TeamMember],
    ) -> None:
        for user in users:
            self._storage.users[user.user_id] = User(
                user_id=user.user_id,
                username=user.username,
                team_name=team_name,
                is_active=user.is_active,
            )

    async def set_active(
        self,
        user_id: str,
        is_active: bool,
    ) -> User | None:
        user = self._storage.users.get(user_id)
        if user is None:
            return None

        updated_user = User(
            user_id=user.user_id,
            username=user.username,
            team_name=user.team_name,
            is_active=is_active,
        )
        self._storage.users[user_id] = updated_user
        return updated_user

    async def list_active_by_team(
        self,
        team_name: str,
        exclude_user_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[User]:
        excluded = exclude_user_ids or set()
        users = [
            user
            for user in self._storage.users.values()
            if user.team_name == team_name
            and user.is_active
            and user.user_id not in excluded
        ]
        users.sort(key=lambda user: user.user_id)
        if limit is not None:
            return users[:limit]
        return users


class InMemoryPullRequestsRepository(IPullRequestsRepository):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage

    async def exists(self, pull_request_id: str) -> bool:
        return pull_request_id in self._storage.pull_requests

    async def get_by_id(self, pull_request_id: str) -> PullRequest | None:
        pull_request = self._storage.pull_requests.get(pull_request_id)
        if pull_request is None:
            return None
        return self._with_reviewers(pull_request)

    async def create(
        self,
        pull_request_id: str,
        pull_request_name: str,
        author_id: str,
    ) -> PullRequest:
        pull_request = PullRequest(
            pull_request_id=pull_request_id,
            pull_request_name=pull_request_name,
            author_id=author_id,
            status=PRStatus.OPEN,
            created_at=datetime.now(UTC),
        )
        self._storage.pull_requests[pull_request_id] = pull_request
        return self._with_reviewers(pull_request)

    async def mark_merged(self, pull_request_id: str) -> PullRequest | None:
        pull_request = self._storage.pull_requests.get(pull_request_id)
        if pull_request is None:
            return None

        if pull_request.status != PRStatus.MERGED:
            pull_request.status = PRStatus.MERGED
            pull_request.merged_at = datetime.now(UTC)

        return self._with_reviewers(pull_request)

    async def list_by_reviewer(self, user_id: str) -> list[PullRequestShort]:
        pull_request_ids = [
            pull_request_id
            for pull_request_id, reviewers in self._storage.reviewers.items()
            if any(reviewer.reviewer_id == user_id for reviewer in reviewers)
        ]
        pull_requests = [
            self._storage.pull_requests[pull_request_id]
            for pull_request_id in pull_request_ids
            if pull_request_id in self._storage.pull_requests
        ]
        pull_requests.sort(key=lambda pr: pr.pull_request_id)
        return [
            PullRequestShort(
                pull_request_id=pr.pull_request_id,
                pull_request_name=pr.pull_request_name,
                author_id=pr.author_id,
                status=pr.status,
            )
            for pr in pull_requests
        ]

    def _with_reviewers(self, pull_request: PullRequest) -> PullRequest:
        reviewers = sorted(
            self._storage.reviewers.get(pull_request.pull_request_id, []),
            key=lambda reviewer: reviewer.slot,
        )
        return PullRequest(
            pull_request_id=pull_request.pull_request_id,
            pull_request_name=pull_request.pull_request_name,
            author_id=pull_request.author_id,
            status=pull_request.status,
            assigned_reviewers=[reviewer.reviewer_id for reviewer in reviewers],
            created_at=pull_request.created_at,
            merged_at=pull_request.merged_at,
        )


class InMemoryPullRequestReviewersRepository(IPullRequestReviewersRepository):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage

    async def list_reviewer_ids(self, pull_request_id: str) -> list[str]:
        reviewers = sorted(
            self._storage.reviewers.get(pull_request_id, []),
            key=lambda reviewer: reviewer.slot,
        )
        return [reviewer.reviewer_id for reviewer in reviewers]

    async def add_reviewers(
        self,
        pull_request_id: str,
        reviewer_ids: list[str],
    ) -> None:
        self._storage.reviewers[pull_request_id] = [
            PullRequestReviewer(
                pull_request_id=pull_request_id,
                reviewer_id=reviewer_id,
                slot=slot,
                assigned_at=datetime.now(UTC),
            )
            for slot, reviewer_id in enumerate(reviewer_ids, start=1)
        ]

    async def is_assigned(
        self,
        pull_request_id: str,
        user_id: str,
    ) -> bool:
        return user_id in await self.list_reviewer_ids(pull_request_id)

    async def replace_reviewer(
        self,
        pull_request_id: str,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        reviewers = self._storage.reviewers.get(pull_request_id, [])
        self._storage.reviewers[pull_request_id] = [
            PullRequestReviewer(
                pull_request_id=reviewer.pull_request_id,
                reviewer_id=(
                    new_user_id
                    if reviewer.reviewer_id == old_user_id
                    else reviewer.reviewer_id
                ),
                slot=reviewer.slot,
                assigned_at=reviewer.assigned_at,
            )
            for reviewer in reviewers
        ]


class InMemoryUnitOfWork(IUnitOfWork):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage
        self.teams = InMemoryTeamsRepository(storage)
        self.users = InMemoryUsersRepository(storage)
        self.pull_requests = InMemoryPullRequestsRepository(storage)
        self.pull_request_reviewers = InMemoryPullRequestReviewersRepository(storage)

    async def __aenter__(self) -> InMemoryUnitOfWork:
        await self._storage.lock.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc is not None:
            await self.rollback()
        self._storage.lock.release()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None
