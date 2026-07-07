from typing import Protocol

from core.domain.entities import AssignmentCount, PullRequestReviewersCount
from core.domain.value_objects import PullRequestReviewerReplacement
from core.interfaces.repositories.base import IRepository


class IPullRequestReviewersRepository(IRepository, Protocol):
    async def list_reviewer_ids(self, pull_request_id: str) -> list[str]: ...

    async def add_reviewers(
        self,
        pull_request_id: str,
        reviewer_ids: list[str],
    ) -> None: ...

    async def is_assigned(
        self,
        pull_request_id: str,
        user_id: str,
    ) -> bool: ...

    async def replace_reviewer(
        self,
        pull_request_id: str,
        old_user_id: str,
        new_user_id: str,
    ) -> None: ...

    async def replace_reviewers(
        self,
        replacements: list[PullRequestReviewerReplacement],
    ) -> None: ...

    async def count(self) -> int: ...

    async def count_by_user(self) -> list[AssignmentCount]: ...

    async def count_by_pull_request(self) -> list[PullRequestReviewersCount]: ...
