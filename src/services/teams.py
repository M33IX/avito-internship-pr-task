from api.v1.teams.schemas import (
    CreateTeamResponse,
    DeactivateTeamRequest,
    DeactivateTeamResponse,
    TeamReviewerReassignment,
)
from api.v1.teams.schemas import (
    Team as TeamSchema,
)
from api.v1.teams.schemas import (
    TeamMember as TeamMemberSchema,
)
from core.application.use_cases import (
    AddTeamCommand,
    DeactivateTeamCommand,
    TeamMemberInput,
    add_team,
    get_team,
)
from core.application.use_cases import (
    deactivate_team as deactivate_team_use_case,
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

    async def deactivate_team(
        self,
        request: DeactivateTeamRequest,
    ) -> DeactivateTeamResponse:
        result = await deactivate_team_use_case(
            command=DeactivateTeamCommand(
                team_name=request.team_name,
                replacement_team_name=request.replacement_team_name,
            ),
            uow=self._uow,
            logger=self._logger,
        )
        return DeactivateTeamResponse(
            team=team_to_schema(result.team),
            reassignments=[
                TeamReviewerReassignment(
                    pull_request_id=reassignment.pull_request_id,
                    old_user_id=reassignment.old_user_id,
                    new_user_id=reassignment.new_user_id,
                )
                for reassignment in result.reassignments
            ],
        )


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
