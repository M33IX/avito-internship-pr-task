from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class TeamMember:
    user_id: str
    username: str
    is_active: bool


@dataclass(slots=True, kw_only=True)
class Team:
    team_name: str
    members: list[TeamMember] = field(default_factory=list[TeamMember])
