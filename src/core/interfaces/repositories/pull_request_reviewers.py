from typing import Protocol

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
