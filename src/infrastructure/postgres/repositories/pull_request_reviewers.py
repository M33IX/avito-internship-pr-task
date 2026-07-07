from sqlalchemy import exists, insert, select, update

from core.interfaces.repositories import IPullRequestReviewersRepository
from infrastructure.postgres.models import PullRequestReviewerModel
from infrastructure.postgres.repositories.base import PostgresRepository


class PostgresPullRequestReviewersRepository(
    PostgresRepository,
    IPullRequestReviewersRepository,
):
    async def list_reviewer_ids(self, pull_request_id: str) -> list[str]:
        stmt = (
            select(PullRequestReviewerModel.reviewer_id)
            .where(PullRequestReviewerModel.pull_request_id == pull_request_id)
            .order_by(PullRequestReviewerModel.slot)
        )
        return list(await self._session.scalars(stmt))

    async def add_reviewers(
        self,
        pull_request_id: str,
        reviewer_ids: list[str],
    ) -> None:
        if not reviewer_ids:
            return

        stmt = insert(PullRequestReviewerModel).values(
            [
                {
                    "pull_request_id": pull_request_id,
                    "reviewer_id": reviewer_id,
                    "slot": slot,
                }
                for slot, reviewer_id in enumerate(reviewer_ids, start=1)
            ]
        )
        await self._session.execute(stmt)

    async def is_assigned(
        self,
        pull_request_id: str,
        user_id: str,
    ) -> bool:
        stmt = select(
            exists().where(
                PullRequestReviewerModel.pull_request_id == pull_request_id,
                PullRequestReviewerModel.reviewer_id == user_id,
            )
        )
        return bool(await self._session.scalar(stmt))

    async def replace_reviewer(
        self,
        pull_request_id: str,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        stmt = (
            update(PullRequestReviewerModel)
            .where(
                PullRequestReviewerModel.pull_request_id == pull_request_id,
                PullRequestReviewerModel.reviewer_id == old_user_id,
            )
            .values(reviewer_id=new_user_id)
        )
        await self._session.execute(stmt)
