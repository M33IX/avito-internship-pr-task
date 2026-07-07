from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.domain.entities import (
    AssignmentCount,
    PullRequest,
    PullRequestReviewer,
    PullRequestReviewersCount,
    PullRequestShort,
    Team,
    TeamMember,
    User,
)
from core.domain.enums.pull_requests import PRStatus
from core.domain.value_objects import PullRequestReviewerReplacement
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

    async def count(self) -> int:
        return len(self._storage.teams)


class InMemoryUsersRepository(IUsersRepository):
    def __init__(self, storage: InMemoryStorage) -> None:
        self._storage = storage

    async def get_by_id(self, user_id: str) -> User | None:
        return self._storage.users.get(user_id)

    async def get_with_active_teammates(
        self,
        user_id: str,
    ) -> tuple[User, list[User]] | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None

        candidates = await self.list_active_by_team(
            team_name=user.team_name,
            exclude_user_ids={user.user_id},
        )
        return user, candidates

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

    async def deactivate_by_team(self, team_name: str) -> None:
        for user_id, user in list(self._storage.users.items()):
            if user.team_name != team_name:
                continue

            self._storage.users[user_id] = User(
                user_id=user.user_id,
                username=user.username,
                team_name=user.team_name,
                is_active=False,
            )

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

    async def count(self) -> int:
        return len(self._storage.users)

    async def count_by_activity(self, *, is_active: bool) -> int:
        return sum(
            1 for user in self._storage.users.values() if user.is_active is is_active
        )


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

    async def get_by_id_for_update(
        self,
        pull_request_id: str,
    ) -> PullRequest | None:
        return await self.get_by_id(pull_request_id)

    async def create(
        self,
        pull_request_id: str,
        pull_request_name: str,
        author_id: str,
    ) -> PullRequest:
        pull_request = await self.create_if_author_exists(
            pull_request_id=pull_request_id,
            pull_request_name=pull_request_name,
            author_id=author_id,
        )
        if pull_request is None:
            raise ValueError("pull request already exists or author is missing")

        return pull_request

    async def create_if_author_exists(
        self,
        pull_request_id: str,
        pull_request_name: str,
        author_id: str,
    ) -> PullRequest | None:
        if pull_request_id in self._storage.pull_requests:
            return None
        if author_id not in self._storage.users:
            return None

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

    async def list_open_by_reviewer_ids(
        self,
        reviewer_ids: set[str],
        *,
        for_update: bool = False,
    ) -> list[PullRequest]:
        del for_update
        if not reviewer_ids:
            return []

        pull_requests = [
            self._storage.pull_requests[pull_request_id]
            for pull_request_id, reviewers in self._storage.reviewers.items()
            if pull_request_id in self._storage.pull_requests
            and self._storage.pull_requests[pull_request_id].status == PRStatus.OPEN
            and any(reviewer.reviewer_id in reviewer_ids for reviewer in reviewers)
        ]
        pull_requests.sort(key=lambda pr: pr.pull_request_id)
        return [self._with_reviewers(pull_request) for pull_request in pull_requests]

    async def count(self) -> int:
        return len(self._storage.pull_requests)

    async def count_by_status(self, status: PRStatus) -> int:
        return sum(
            1 for pr in self._storage.pull_requests.values() if pr.status == status
        )

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
        await self.replace_reviewers(
            [
                PullRequestReviewerReplacement(
                    pull_request_id=pull_request_id,
                    old_user_id=old_user_id,
                    new_user_id=new_user_id,
                )
            ]
        )

    async def replace_reviewers(
        self,
        replacements: list[PullRequestReviewerReplacement],
    ) -> None:
        replacements_by_key = {
            (replacement.pull_request_id, replacement.old_user_id): replacement
            for replacement in replacements
        }
        if not replacements_by_key:
            return

        for pull_request_id, reviewers in list(self._storage.reviewers.items()):
            if not any(
                (pull_request_id, reviewer.reviewer_id) in replacements_by_key
                for reviewer in reviewers
            ):
                continue

            self._storage.reviewers[pull_request_id] = [
                PullRequestReviewer(
                    pull_request_id=reviewer.pull_request_id,
                    reviewer_id=replacements_by_key[
                        (pull_request_id, reviewer.reviewer_id)
                    ].new_user_id
                    if (pull_request_id, reviewer.reviewer_id) in replacements_by_key
                    else reviewer.reviewer_id,
                    slot=reviewer.slot,
                    assigned_at=reviewer.assigned_at,
                )
                for reviewer in reviewers
            ]

    async def count(self) -> int:
        return sum(len(reviewers) for reviewers in self._storage.reviewers.values())

    async def count_by_user(self) -> list[AssignmentCount]:
        counts: dict[str, int] = {}
        for reviewers in self._storage.reviewers.values():
            for reviewer in reviewers:
                counts[reviewer.reviewer_id] = counts.get(reviewer.reviewer_id, 0) + 1

        return [
            AssignmentCount(user_id=user_id, pull_requests=pull_requests)
            for user_id, pull_requests in sorted(counts.items())
        ]

    async def count_by_pull_request(self) -> list[PullRequestReviewersCount]:
        return [
            PullRequestReviewersCount(
                pull_request_id=pull_request_id,
                reviewers=len(reviewers),
            )
            for pull_request_id, reviewers in sorted(self._storage.reviewers.items())
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
