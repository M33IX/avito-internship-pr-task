from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from api.v1.pull_requests.schemas import (
    CreatePrRequest,
    MergePrRequest,
    ReassignPrRequest,
)
from api.v1.teams.schemas import Team, TeamMember
from api.v1.users.schemas import SetIsActiveRequest
from core.domain.constraints import (
    PULL_REQUEST_ID_LENGTH,
    PULL_REQUEST_NAME_LENGTH,
    TEAM_NAME_LENGTH,
    USER_ID_LENGTH,
    USERNAME_LENGTH,
)

pytestmark = pytest.mark.unit


def too_long(length: int) -> str:
    return "x" * (length + 1)


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {
                "team_name": too_long(TEAM_NAME_LENGTH),
                "members": [{"user_id": "u1", "username": "Alice", "is_active": True}],
            },
            "team_name",
        ),
        (
            {
                "team_name": "backend",
                "members": [
                    {
                        "user_id": too_long(USER_ID_LENGTH),
                        "username": "Alice",
                        "is_active": True,
                    }
                ],
            },
            "user_id",
        ),
        (
            {
                "team_name": "backend",
                "members": [
                    {
                        "user_id": "u1",
                        "username": too_long(USERNAME_LENGTH),
                        "is_active": True,
                    }
                ],
            },
            "username",
        ),
    ],
)
def test_team_request_rejects_values_longer_than_database_columns(
    payload: dict[str, object],
    field: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Team.model_validate(payload)

    assert field in str(exc_info.value)


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (
            CreatePrRequest,
            {
                "pull_request_id": too_long(PULL_REQUEST_ID_LENGTH),
                "pull_request_name": "Add search",
                "author_id": "u1",
            },
            "pull_request_id",
        ),
        (
            CreatePrRequest,
            {
                "pull_request_id": "pr1",
                "pull_request_name": too_long(PULL_REQUEST_NAME_LENGTH),
                "author_id": "u1",
            },
            "pull_request_name",
        ),
        (
            CreatePrRequest,
            {
                "pull_request_id": "pr1",
                "pull_request_name": "Add search",
                "author_id": too_long(USER_ID_LENGTH),
            },
            "author_id",
        ),
        (
            MergePrRequest,
            {"pull_request_id": too_long(PULL_REQUEST_ID_LENGTH)},
            "pull_request_id",
        ),
        (
            ReassignPrRequest,
            {"pull_request_id": "pr1", "old_user_id": too_long(USER_ID_LENGTH)},
            "old_user_id",
        ),
        (
            SetIsActiveRequest,
            {"user_id": too_long(USER_ID_LENGTH), "is_active": True},
            "user_id",
        ),
    ],
)
def test_request_models_reject_values_longer_than_database_columns(
    model: BaseModel,
    payload: dict[str, object],
    field: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)

    assert field in str(exc_info.value)


def test_request_models_reject_blank_strings_after_strip() -> None:
    with pytest.raises(ValidationError):
        TeamMember.model_validate(
            {
                "user_id": "   ",
                "username": "Alice",
                "is_active": True,
            }
        )


def test_request_models_strip_surrounding_whitespace() -> None:
    request = CreatePrRequest.model_validate(
        {
            "pull_request_id": "  pr1  ",
            "pull_request_name": "  Add search  ",
            "author_id": "  u1  ",
        }
    )

    assert request.pull_request_id == "pr1"
    assert request.pull_request_name == "Add search"
    assert request.author_id == "u1"
