from typing import Protocol

from core.interfaces.repositories import (
    IPullRequestReviewersRepository,
    IPullRequestsRepository,
    ITeamsRepository,
    IUsersRepository,
)


class IUnitOfWork(Protocol):
    teams: ITeamsRepository
    users: IUsersRepository
    pull_requests: IPullRequestsRepository
    pull_request_reviewers: IPullRequestReviewersRepository

    async def __aenter__(self) -> IUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
