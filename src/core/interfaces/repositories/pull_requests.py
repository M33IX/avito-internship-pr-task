from core.domain.entities import PullRequest, PullRequestShort
from core.interfaces.repositories.base import IRepository


class IPullRequestsRepository(IRepository):
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

    async def mark_merged(self, pull_request_id: str) -> PullRequest | None: ...

    async def list_by_reviewer(self, user_id: str) -> list[PullRequestShort]: ...
