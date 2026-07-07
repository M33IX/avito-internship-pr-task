from collections.abc import Mapping
from typing import Any

from sqlalchemy import case, exists, func, insert, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.engine import RowMapping

from core.domain.entities import PullRequest, PullRequestShort
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.repositories import IPullRequestsRepository
from infrastructure.postgres.models import (
    PullRequestModel,
    PullRequestReviewerModel,
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
        stmt = (
            insert(PullRequestModel)
            .values(
                pull_request_id=pull_request_id,
                pull_request_name=pull_request_name,
                author_id=author_id,
                status=PRStatus.OPEN,
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
        row = (await self._session.execute(stmt)).mappings().one()
        return _pull_request_from_row({**row, "assigned_reviewers": []})

    async def mark_merged(self, pull_request_id: str) -> PullRequest | None:
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
            .returning(PullRequestModel.pull_request_id)
        )
        updated_pull_request_id = await self._session.scalar(stmt)
        if updated_pull_request_id is None:
            return None
        return await self.get_by_id(updated_pull_request_id)

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


def _select_pull_request_by_id(
    pull_request_id: str,
    *,
    for_update: bool = False,
):
    reviewers = (
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
