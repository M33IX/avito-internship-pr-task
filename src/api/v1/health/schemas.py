from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(BaseModel):
    status: HealthStatus
    database: HealthStatus

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": HealthStatus.OK,
                "database": HealthStatus.OK,
            }
        }
    )


class AssignmentCountResponse(BaseModel):
    user_id: str
    pull_requests: int


class PullRequestReviewersCountResponse(BaseModel):
    pull_request_id: str
    reviewers: int


class StatsResponse(BaseModel):
    teams: int
    users: int
    active_users: int
    inactive_users: int
    pull_requests: int
    open_pull_requests: int
    merged_pull_requests: int
    assignments: int
    assignments_by_user: list[AssignmentCountResponse]
    reviewers_by_pull_request: list[PullRequestReviewersCountResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "teams": 2,
                "users": 10,
                "active_users": 8,
                "inactive_users": 2,
                "pull_requests": 4,
                "open_pull_requests": 3,
                "merged_pull_requests": 1,
                "assignments": 6,
                "assignments_by_user": [
                    {"user_id": "u2", "pull_requests": 2},
                ],
                "reviewers_by_pull_request": [
                    {"pull_request_id": "pr-1001", "reviewers": 2},
                ],
            }
        }
    )
