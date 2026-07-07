from sqlalchemy import exists, insert, select

from core.domain.entities import Team, TeamMember
from core.interfaces.repositories import ITeamsRepository
from infrastructure.postgres.models import TeamModel, UserModel
from infrastructure.postgres.repositories.base import PostgresRepository


class PostgresTeamsRepository(PostgresRepository, ITeamsRepository):
    async def exists(self, team_name: str) -> bool:
        stmt = select(exists().where(TeamModel.team_name == team_name))
        return bool(await self._session.scalar(stmt))

    async def get_by_name(self, team_name: str) -> Team | None:
        stmt = (
            select(
                TeamModel.team_name,
                UserModel.user_id,
                UserModel.username,
                UserModel.is_active,
            )
            .outerjoin(UserModel, UserModel.team_name == TeamModel.team_name)
            .where(TeamModel.team_name == team_name)
            .order_by(UserModel.user_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        if not rows:
            return None

        return Team(
            team_name=rows[0]["team_name"],
            members=[
                TeamMember(
                    user_id=row["user_id"],
                    username=row["username"],
                    is_active=row["is_active"],
                )
                for row in rows
                if row["user_id"] is not None
            ],
        )

    async def create(self, team_name: str) -> None:
        stmt = insert(TeamModel).values(team_name=team_name)
        await self._session.execute(stmt)
