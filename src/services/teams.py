from api.v1.teams.schemas import CreateTeamResponse, Team


class TeamsService:
    async def get_team(self, team_name: str) -> Team: ...

    async def add_team(self, team: Team) -> CreateTeamResponse: ...
