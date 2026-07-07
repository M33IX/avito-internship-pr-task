from typing import Protocol

from core.domain.entities import PullRequest, PullRequestShort
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.repositories.base import IRepository


class IPullRequestsRepository(IRepository, Protocol):
    async def exists(self, pull_request_id: str) -> bool: ...

    async def get_by_id(self, pull_request_id: str) -> PullRequest | None: ...

    async def get_by_id_for_update(
        self,
        pull_request_id: str,
    ) -> PullRequest | None: ...

    async def create(
        self,
        pull_request_id: str,
        pull_request_name: str,
        author_id: str,
    ) -> PullRequest: ...

    async def create_if_author_exists(
        self,
        pull_request_id: str,
        pull_request_name: str,
        author_id: str,
    ) -> PullRequest | None: ...

    async def mark_merged(self, pull_request_id: str) -> PullRequest | None: ...

    async def list_by_reviewer(self, user_id: str) -> list[PullRequestShort]: ...

    async def list_open_by_reviewer_ids(
        self,
        reviewer_ids: set[str],
        *,
        for_update: bool = False,
    ) -> list[PullRequest]: ...

    async def count(self) -> int: ...

    async def count_by_status(self, status: PRStatus) -> int: ...
