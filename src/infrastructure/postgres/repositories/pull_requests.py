from collections.abc import Mapping
from typing import Any

from sqlalchemy import case, exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping

from core.domain.entities import PullRequest, PullRequestShort
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.repositories import IPullRequestsRepository
from infrastructure.postgres.models import (
    PullRequestModel,
    PullRequestReviewerModel,
    UserModel,
)
from infrastructure.postgres.repositories.base import PostgresRepository

type RowData = Mapping[str, Any] | RowMapping


class PostgresPullRequestsRepository(PostgresRepository, IPullRequestsRepository):
    async def exists(self, pull_request_id: str) -> bool:
        stmt = select(
            exists().where(PullRequestModel.pull_request_id == pull_request_id)
        )
        return bool(await self._session.scalar(stmt))

    async def get_by_id(self, pull_request_id: str) -> PullRequest | None:
        result = await self._session.execute(
            _select_pull_request_by_id(pull_request_id=pull_request_id)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _pull_request_from_row(row)

    async def get_by_id_for_update(
        self,
        pull_request_id: str,
    ) -> PullRequest | None:
        result = await self._session.execute(
            _select_pull_request_by_id(
                pull_request_id=pull_request_id,
                for_update=True,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _pull_request_from_row(row)

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
        values = select(
            literal(pull_request_id),
            literal(pull_request_name),
            UserModel.user_id,
            literal(PRStatus.OPEN),
        ).where(UserModel.user_id == author_id)
        stmt = (
            pg_insert(PullRequestModel)
            .from_select(
                [
                    PullRequestModel.pull_request_id,
                    PullRequestModel.pull_request_name,
                    PullRequestModel.author_id,
                    PullRequestModel.status,
                ],
                values,
            )
            .on_conflict_do_nothing(
                index_elements=[PullRequestModel.pull_request_id],
            )
            .returning(
                PullRequestModel.pull_request_id,
                PullRequestModel.pull_request_name,
                PullRequestModel.author_id,
                PullRequestModel.status,
                PullRequestModel.created_at,
                PullRequestModel.merged_at,
            )
        )
        row = (await self._session.execute(stmt)).mappings().one_or_none()
        if row is None:
            return None
        return _pull_request_from_row({**row, "assigned_reviewers": []})

    async def mark_merged(self, pull_request_id: str) -> PullRequest | None:
        reviewers = _reviewers_aggregation()
        stmt = (
            update(PullRequestModel)
            .where(PullRequestModel.pull_request_id == pull_request_id)
            .values(
                status=PRStatus.MERGED,
                merged_at=case(
                    (
                        PullRequestModel.status == PRStatus.MERGED,
                        PullRequestModel.merged_at,
                    ),
                    else_=func.now(),
                ),
            )
            .returning(
                PullRequestModel.pull_request_id,
                PullRequestModel.pull_request_name,
                PullRequestModel.author_id,
                PullRequestModel.status,
                PullRequestModel.created_at,
                PullRequestModel.merged_at,
            )
            .cte("updated_pull_request")
        )
        result = await self._session.execute(
            select(
                stmt.c.pull_request_id,
                stmt.c.pull_request_name,
                stmt.c.author_id,
                stmt.c.status,
                stmt.c.created_at,
                stmt.c.merged_at,
                reviewers.c.assigned_reviewers,
            ).outerjoin(
                reviewers,
                reviewers.c.pull_request_id == stmt.c.pull_request_id,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _pull_request_from_row(row)

    async def list_by_reviewer(self, user_id: str) -> list[PullRequestShort]:
        stmt = (
            select(
                PullRequestModel.pull_request_id,
                PullRequestModel.pull_request_name,
                PullRequestModel.author_id,
                PullRequestModel.status,
            )
            .join(
                PullRequestReviewerModel,
                (
                    PullRequestReviewerModel.pull_request_id
                    == PullRequestModel.pull_request_id
                ),
            )
            .where(PullRequestReviewerModel.reviewer_id == user_id)
            .order_by(PullRequestModel.pull_request_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [_pull_request_short_from_row(row) for row in rows]

    async def list_open_by_reviewer_ids(
        self,
        reviewer_ids: set[str],
        *,
        for_update: bool = False,
    ) -> list[PullRequest]:
        if not reviewer_ids:
            return []

        reviewers = _reviewers_aggregation()
        target_pull_request_ids = (
            select(PullRequestReviewerModel.pull_request_id)
            .where(PullRequestReviewerModel.reviewer_id.in_(reviewer_ids))
            .subquery()
        )
        stmt = (
            select(
                PullRequestModel.pull_request_id,
                PullRequestModel.pull_request_name,
                PullRequestModel.author_id,
                PullRequestModel.status,
                PullRequestModel.created_at,
                PullRequestModel.merged_at,
                reviewers.c.assigned_reviewers,
            )
            .outerjoin(
                reviewers,
                reviewers.c.pull_request_id == PullRequestModel.pull_request_id,
            )
            .where(
                PullRequestModel.status == PRStatus.OPEN,
                PullRequestModel.pull_request_id.in_(
                    select(target_pull_request_ids.c.pull_request_id)
                ),
            )
            .order_by(PullRequestModel.pull_request_id)
        )
        if for_update:
            stmt = stmt.with_for_update(of=PullRequestModel.__table__)

        rows = (await self._session.execute(stmt)).mappings().all()
        return [_pull_request_from_row(row) for row in rows]

    async def count(self) -> int:
        stmt = select(func.count()).select_from(PullRequestModel)
        return int(await self._session.scalar(stmt) or 0)

    async def count_by_status(self, status: PRStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(PullRequestModel)
            .where(PullRequestModel.status == status)
        )
        return int(await self._session.scalar(stmt) or 0)


def _select_pull_request_by_id(
    pull_request_id: str,
    *,
    for_update: bool = False,
):
    reviewers = _reviewers_aggregation()
    stmt = (
        select(
            PullRequestModel.pull_request_id,
            PullRequestModel.pull_request_name,
            PullRequestModel.author_id,
            PullRequestModel.status,
            PullRequestModel.created_at,
            PullRequestModel.merged_at,
            reviewers.c.assigned_reviewers,
        )
        .outerjoin(
            reviewers,
            reviewers.c.pull_request_id == PullRequestModel.pull_request_id,
        )
        .where(PullRequestModel.pull_request_id == pull_request_id)
    )
    if for_update:
        stmt = stmt.with_for_update(of=PullRequestModel.__table__)
    return stmt


def _reviewers_aggregation():
    return (
        select(
            PullRequestReviewerModel.pull_request_id,
            func.array_agg(
                aggregate_order_by(
                    PullRequestReviewerModel.reviewer_id,
                    PullRequestReviewerModel.slot,
                )
            ).label("assigned_reviewers"),
        )
        .group_by(PullRequestReviewerModel.pull_request_id)
        .subquery()
    )


def _pull_request_from_row(row: RowData) -> PullRequest:
    return PullRequest(
        pull_request_id=row["pull_request_id"],
        pull_request_name=row["pull_request_name"],
        author_id=row["author_id"],
        status=_pr_status(row["status"]),
        assigned_reviewers=list(row["assigned_reviewers"] or []),
        created_at=row["created_at"],
        merged_at=row["merged_at"],
    )


def _pull_request_short_from_row(row: RowData) -> PullRequestShort:
    return PullRequestShort(
        pull_request_id=row["pull_request_id"],
        pull_request_name=row["pull_request_name"],
        author_id=row["author_id"],
        status=_pr_status(row["status"]),
    )


def _pr_status(status: PRStatus | str) -> PRStatus:
    if isinstance(status, PRStatus):
        return status
    return PRStatus(status)
