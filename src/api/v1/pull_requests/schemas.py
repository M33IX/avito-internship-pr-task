from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.domain.enums.pull_requests import PRStatus


class PullRequestShort(BaseModel):
    pull_request_id: str
    pull_request_name: str
    author_id: str
    status: PRStatus = Field(examples=[PRStatus.OPEN])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
                "pull_request_name": "Add search",
                "author_id": "u1",
                "status": PRStatus.OPEN,
            }
        }
    )


class CreatePrRequest(BaseModel):
    pull_request_id: str = Field(examples=["pr-1001"])
    pull_request_name: str = Field(examples=["Add search"])
    author_id: str = Field(examples=["u1"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
                "pull_request_name": "Add search",
                "author_id": "u1",
            }
        }
    )


class PullRequest(PullRequestShort):
    assigned_reviewers: list[str]
    created_at: datetime | None = Field(default=None, alias="createdAt")
    merged_at: datetime | None = Field(default=None, alias="mergedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
                "pull_request_name": "Add search",
                "author_id": "u1",
                "status": PRStatus.OPEN,
                "assigned_reviewers": ["u2", "u3"],
                "createdAt": None,
                "mergedAt": None,
            }
        },
    )


class CreatePrResponse(BaseModel):
    pr: PullRequest

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pr": {
                    "pull_request_id": "pr-1001",
                    "pull_request_name": "Add search",
                    "author_id": "u1",
                    "status": PRStatus.OPEN,
                    "assigned_reviewers": ["u2", "u3"],
                }
            }
        }
    )


class MergePrRequest(BaseModel):
    pull_request_id: str = Field(examples=["pr-1001"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
            }
        }
    )


class MergePrResponse(BaseModel):
    pr: PullRequest

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pr": {
                    "pull_request_id": "pr-1001",
                    "pull_request_name": "Add search",
                    "author_id": "u1",
                    "status": PRStatus.MERGED,
                    "assigned_reviewers": ["u2", "u3"],
                    "mergedAt": "2025-10-24T12:34:56Z",
                }
            }
        }
    )


class ReassignPrRequest(BaseModel):
    pull_request_id: str = Field(examples=["pr-1001"])
    old_user_id: str = Field(examples=["u2"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pull_request_id": "pr-1001",
                "old_user_id": "u2",
            }
        }
    )


class ReassignPrResponse(CreatePrResponse):
    replaced_by: str = Field(examples=["u5"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pr": {
                    "pull_request_id": "pr-1001",
                    "pull_request_name": "Add search",
                    "author_id": "u1",
                    "status": PRStatus.OPEN,
                    "assigned_reviewers": ["u3", "u5"],
                },
                "replaced_by": "u5",
            }
        }
    )
