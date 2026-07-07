from pydantic import BaseModel, ConfigDict, Field

from api.v1.validation import PullRequestId, TeamName, UserId, Username


class TeamMember(BaseModel):
    user_id: UserId = Field(examples=["u1"])
    username: Username = Field(examples=["Alice"])
    is_active: bool = Field(examples=[True])


class Team(BaseModel):
    team_name: TeamName = Field(examples=["payments"])
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


class DeactivateTeamRequest(BaseModel):
    team_name: TeamName = Field(examples=["backend"])
    replacement_team_name: TeamName = Field(examples=["platform"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team_name": "backend",
                "replacement_team_name": "platform",
            }
        }
    )


class TeamReviewerReassignment(BaseModel):
    pull_request_id: PullRequestId = Field(examples=["pr-1001"])
    old_user_id: UserId = Field(examples=["u2"])
    new_user_id: UserId = Field(examples=["p1"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
                "old_user_id": "u2",
                "new_user_id": "p1",
            }
        }
    )


class DeactivateTeamResponse(BaseModel):
    team: Team
    reassignments: list[TeamReviewerReassignment]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team": {
                    "team_name": "backend",
                    "members": [
                        {
                            "user_id": "u1",
                            "username": "Alice",
                            "is_active": False,
                        },
                        {
                            "user_id": "u2",
                            "username": "Bob",
                            "is_active": False,
                        },
                    ],
                },
                "reassignments": [
                    {
                        "pull_request_id": "pr-1001",
                        "old_user_id": "u2",
                        "new_user_id": "p1",
                    }
                ],
            }
        }
    )
