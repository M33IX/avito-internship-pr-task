from pydantic import BaseModel, ConfigDict, Field


class TeamMember(BaseModel):
    user_id: str = Field(examples=["u1"])
    username: str = Field(examples=["Alice"])
    is_active: bool = Field(examples=[True])


class Team(BaseModel):
    team_name: str = Field(examples=["payments"])
    members: list[TeamMember] = Field(
        examples=[
            [
                TeamMember(user_id="u1", username="Alice", is_active=True),
                TeamMember(user_id="u2", username="Bob", is_active=True),
            ]
        ]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team_name": "payments",
                "members": [
                    {
                        "user_id": "u1",
                        "username": "Alice",
                        "is_active": True,
                    },
                    {
                        "user_id": "u2",
                        "username": "Bob",
                        "is_active": True,
                    },
                ],
            }
        }
    )


class CreateTeamResponse(BaseModel):
    team: Team

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team": {
                    "team_name": "backend",
                    "members": [
                        {
                            "user_id": "u1",
                            "username": "Alice",
                            "is_active": True,
                        },
                        {
                            "user_id": "u2",
                            "username": "Bob",
                            "is_active": True,
                        },
                    ],
                }
            }
        }
    )
