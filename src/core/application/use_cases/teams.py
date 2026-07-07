from dataclasses import dataclass

from core.domain.entities import Team, TeamMember
from core.exceptions import TeamAlreadyExistsError, TeamNotFoundError
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


@dataclass(slots=True, kw_only=True)
class TeamMemberInput:
    user_id: str
    username: str
    is_active: bool


@dataclass(slots=True, kw_only=True)
class AddTeamCommand:
    team_name: str
    members: list[TeamMemberInput]


async def get_team(
    team_name: str,
    uow: IUnitOfWork,
    logger: ILogger,
) -> Team:
    team = await uow.teams.get_by_name(team_name)
    if team is None:
        logger.warning("team not found", team_name=team_name)
        raise TeamNotFoundError("resource not found")

    return team


async def add_team(
    command: AddTeamCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> Team:
    if await uow.teams.exists(command.team_name):
        logger.warning("team already exists", team_name=command.team_name)
        raise TeamAlreadyExistsError("team_name already exists")

    await uow.teams.create(command.team_name)
    await uow.users.upsert_many(
        team_name=command.team_name,
        users=[
            TeamMember(
                user_id=member.user_id,
                username=member.username,
                is_active=member.is_active,
            )
            for member in command.members
        ],
    )
    await uow.commit()

    created_team = await uow.teams.get_by_name(command.team_name)
    if created_team is None:
        logger.error("created team not found", team_name=command.team_name)
        raise TeamNotFoundError("resource not found")

    logger.info(
        "team created",
        team_name=created_team.team_name,
        members_count=len(created_team.members),
    )
    return created_team
