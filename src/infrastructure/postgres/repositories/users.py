from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping

from core.domain.entities import TeamMember, User
from core.interfaces.repositories import IUsersRepository
from infrastructure.postgres.models import UserModel
from infrastructure.postgres.repositories.base import PostgresRepository

type RowData = Mapping[str, Any] | RowMapping


class PostgresUsersRepository(PostgresRepository, IUsersRepository):
    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(
                UserModel.user_id,
                UserModel.username,
                UserModel.team_name,
                UserModel.is_active,
            )
            .where(UserModel.user_id == user_id)
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().one_or_none()
        if row is None:
            return None
        return _user_from_row(row)

    async def get_with_active_teammates(
        self,
        user_id: str,
    ) -> tuple[User, list[User]] | None:
        author = (
            select(
                UserModel.user_id,
                UserModel.username,
                UserModel.team_name,
                UserModel.is_active,
            )
            .where(UserModel.user_id == user_id)
            .cte("author")
        )
        stmt = (
            select(
                author.c.user_id.label("author_user_id"),
                author.c.username.label("author_username"),
                author.c.team_name.label("author_team_name"),
                author.c.is_active.label("author_is_active"),
                UserModel.user_id.label("candidate_user_id"),
                UserModel.username.label("candidate_username"),
                UserModel.team_name.label("candidate_team_name"),
                UserModel.is_active.label("candidate_is_active"),
            )
            .select_from(author)
            .outerjoin(
                UserModel,
                and_(
                    UserModel.team_name == author.c.team_name,
                    UserModel.is_active.is_(True),
                    UserModel.user_id != author.c.user_id,
                ),
            )
            .order_by(UserModel.user_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        if not rows:
            return None

        author_user = User(
            user_id=rows[0]["author_user_id"],
            username=rows[0]["author_username"],
            team_name=rows[0]["author_team_name"],
            is_active=rows[0]["author_is_active"],
        )
        candidates = [
            User(
                user_id=row["candidate_user_id"],
                username=row["candidate_username"],
                team_name=row["candidate_team_name"],
                is_active=row["candidate_is_active"],
            )
            for row in rows
            if row["candidate_user_id"] is not None
        ]
        return author_user, candidates

    async def upsert_many(
        self,
        team_name: str,
        users: list[TeamMember],
    ) -> None:
        if not users:
            return

        stmt = insert(UserModel).values(
            [
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "team_name": team_name,
                    "is_active": user.is_active,
                }
                for user in users
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserModel.user_id],
            set_={
                "username": stmt.excluded.username,
                "team_name": stmt.excluded.team_name,
                "is_active": stmt.excluded.is_active,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)

    async def set_active(
        self,
        user_id: str,
        is_active: bool,
    ) -> User | None:
        stmt = (
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(
                is_active=is_active,
                updated_at=func.now(),
            )
            .returning(
                UserModel.user_id,
                UserModel.username,
                UserModel.team_name,
                UserModel.is_active,
            )
        )
        row = (await self._session.execute(stmt)).mappings().one_or_none()
        if row is None:
            return None
        return _user_from_row(row)

    async def deactivate_by_team(self, team_name: str) -> None:
        stmt = (
            update(UserModel)
            .where(
                UserModel.team_name == team_name,
                UserModel.is_active.is_(True),
            )
            .values(
                is_active=False,
                updated_at=func.now(),
            )
        )
        await self._session.execute(stmt)

    async def list_active_by_team(
        self,
        team_name: str,
        exclude_user_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[User]:
        stmt = (
            select(
                UserModel.user_id,
                UserModel.username,
                UserModel.team_name,
                UserModel.is_active,
            )
            .where(
                UserModel.team_name == team_name,
                UserModel.is_active.is_(True),
            )
            .order_by(UserModel.user_id)
        )
        if exclude_user_ids:
            stmt = stmt.where(~UserModel.user_id.in_(exclude_user_ids))
        if limit is not None:
            stmt = stmt.limit(limit)

        rows = (await self._session.execute(stmt)).mappings().all()
        return [_user_from_row(row) for row in rows]

    async def count(self) -> int:
        stmt = select(func.count()).select_from(UserModel)
        return int(await self._session.scalar(stmt) or 0)

    async def count_by_activity(self, *, is_active: bool) -> int:
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.is_active.is_(is_active))
        )
        return int(await self._session.scalar(stmt) or 0)


def _user_from_row(row: RowData) -> User:
    return User(
        user_id=row["user_id"],
        username=row["username"],
        team_name=row["team_name"],
        is_active=row["is_active"],
    )
