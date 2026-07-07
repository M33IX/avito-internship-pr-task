from api.v1.teams.schemas import (
    CreateTeamResponse,
)
from api.v1.teams.schemas import (
    Team as TeamSchema,
)
from api.v1.teams.schemas import (
    TeamMember as TeamMemberSchema,
)
from core.application.use_cases import (
    AddTeamCommand,
    TeamMemberInput,
    add_team,
    get_team,
)
from core.domain.entities import Team
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


class TeamsService:
    def __init__(
        self,
        uow: IUnitOfWork,
        logger: ILogger,
    ) -> None:
        self._uow = uow
        self._logger = logger

    async def get_team(self, team_name: str) -> TeamSchema:
        team = await get_team(
            team_name=team_name,
            uow=self._uow,
            logger=self._logger,
        )
        return team_to_schema(team)

    async def add_team(self, team: TeamSchema) -> CreateTeamResponse:
        created_team = await add_team(
            command=AddTeamCommand(
                team_name=team.team_name,
                members=[
                    TeamMemberInput(
                        user_id=member.user_id,
                        username=member.username,
                        is_active=member.is_active,
                    )
                    for member in team.members
                ],
            ),
            uow=self._uow,
            logger=self._logger,
        )
        return CreateTeamResponse(team=team_to_schema(created_team))


def team_to_schema(team: Team) -> TeamSchema:
    return TeamSchema(
        team_name=team.team_name,
        members=[
            TeamMemberSchema(
                user_id=member.user_id,
                username=member.username,
                is_active=member.is_active,
            )
            for member in team.members
        ],
    )
