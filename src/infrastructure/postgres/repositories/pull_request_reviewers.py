from typing import cast

from sqlalchemy import Table, bindparam, exists, func, insert, select, update

from core.domain.entities import AssignmentCount, PullRequestReviewersCount
from core.domain.value_objects import PullRequestReviewerReplacement
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

    async def count(self) -> int:
        stmt = select(func.count()).select_from(PullRequestReviewerModel)
        return int(await self._session.scalar(stmt) or 0)

    async def count_by_user(self) -> list[AssignmentCount]:
        stmt = (
            select(
                PullRequestReviewerModel.reviewer_id,
                func.count(PullRequestReviewerModel.pull_request_id).label(
                    "pull_requests"
                ),
            )
            .group_by(PullRequestReviewerModel.reviewer_id)
            .order_by(PullRequestReviewerModel.reviewer_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            AssignmentCount(
                user_id=row["reviewer_id"],
                pull_requests=row["pull_requests"],
            )
            for row in rows
        ]

    async def count_by_pull_request(self) -> list[PullRequestReviewersCount]:
        stmt = (
            select(
                PullRequestReviewerModel.pull_request_id,
                func.count(PullRequestReviewerModel.reviewer_id).label("reviewers"),
            )
            .group_by(PullRequestReviewerModel.pull_request_id)
            .order_by(PullRequestReviewerModel.pull_request_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PullRequestReviewersCount(
                pull_request_id=row["pull_request_id"],
                reviewers=row["reviewers"],
            )
            for row in rows
        ]

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
        if not replacements:
            return

        table = cast(Table, PullRequestReviewerModel.__table__)
        stmt = (
            update(table)
            .where(
                table.c.pull_request_id == bindparam("target_pull_request_id"),
                table.c.reviewer_id == bindparam("target_old_user_id"),
            )
            .values(reviewer_id=bindparam("target_new_user_id"))
        )
        await self._session.execute(
            stmt,
            [
                {
                    "target_pull_request_id": replacement.pull_request_id,
                    "target_old_user_id": replacement.old_user_id,
                    "target_new_user_id": replacement.new_user_id,
                }
                for replacement in replacements
            ],
        )
