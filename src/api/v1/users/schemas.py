from pydantic import BaseModel, ConfigDict, Field

from api.v1.pull_requests.schemas import PullRequestShort
from api.v1.validation import TeamName, UserId, Username


class User(BaseModel):
    user_id: UserId = Field(examples=["u2"])
    username: Username = Field(examples=["Bob"])
    team_name: TeamName = Field(examples=["backend"])
    is_active: bool = Field(examples=[True])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "u2",
                "username": "Bob",
                "team_name": "backend",
                "is_active": True,
            }
        }
    )


class SetIsActiveRequest(BaseModel):
    user_id: UserId = Field(examples=["u2"])
    is_active: bool = Field(examples=[False])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "u2",
                "is_active": False,
            }
        }
    )


class SetIsActiveResponse(BaseModel):
    user: User

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "user_id": "u2",
                    "username": "Bob",
                    "team_name": "backend",
                    "is_active": False,
                }
            }
        }
    )


class GetReviewResponse(BaseModel):
    user_id: UserId
    pull_requests: list[PullRequestShort]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "u2",
                "pull_requests": [
                    {
                        "pull_request_id": "pr-1001",
                        "pull_request_name": "Add search",
                        "author_id": "u1",
                        "status": "OPEN",
                    }
                ],
            }
        }
    )
