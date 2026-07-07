from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class User:
    user_id: str
    username: str
    team_name: str
    is_active: bool
