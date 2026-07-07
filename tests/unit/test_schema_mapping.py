from __future__ import annotations

from datetime import UTC, datetime

import pytest

from api.v1.pull_requests.schemas import PullRequestShort as PullRequestShortSchema
from core.domain.entities import PullRequestShort, Team
from core.domain.enums.pull_requests import PRStatus
from services.pull_requests import pull_request_to_schema
from services.teams import team_to_schema
from services.users import pull_request_short_to_schema, user_to_schema
from tests.factories import domain_pull_request, domain_team_members, domain_user

pytestmark = pytest.mark.unit


def test_pull_request_schema_uses_contract_aliases() -> None:
    created_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    merged_at = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

    schema = pull_request_to_schema(
        domain_pull_request(
            status=PRStatus.MERGED,
            created_at=created_at,
            merged_at=merged_at,
        )
    )
    payload = schema.model_dump(mode="json", by_alias=True)

    assert payload["createdAt"] == "2026-01-01T12:00:00Z"
    assert payload["mergedAt"] == "2026-01-02T12:00:00Z"
    assert "created_at" not in payload
    assert "merged_at" not in payload
    assert payload["status"] == "MERGED"


def test_team_to_schema_returns_contract_shape() -> None:
    schema = team_to_schema(
        team=Team(
            team_name="backend",
            members=domain_team_members(),
        )
    )

    assert schema.model_dump(mode="json") == {
        "team_name": "backend",
        "members": [
            {"user_id": "u1", "username": "Author", "is_active": True},
            {"user_id": "u2", "username": "Reviewer Two", "is_active": True},
            {"user_id": "u3", "username": "Reviewer Three", "is_active": True},
            {"user_id": "u4", "username": "Replacement", "is_active": True},
            {"user_id": "u5", "username": "Inactive", "is_active": False},
        ],
    }


def test_user_to_schema_returns_contract_shape() -> None:
    schema = user_to_schema(
        domain_user(
            user_id="u2",
            username="Reviewer Two",
            team_name="backend",
            is_active=False,
        )
    )

    assert schema.model_dump(mode="json") == {
        "user_id": "u2",
        "username": "Reviewer Two",
        "team_name": "backend",
        "is_active": False,
    }


def test_pull_request_short_to_schema_returns_contract_shape() -> None:
    schema = pull_request_short_to_schema(
        PullRequestShort(
            pull_request_id="pr1",
            pull_request_name="Add search",
            author_id="u1",
            status=PRStatus.OPEN,
        )
    )

    assert isinstance(schema, PullRequestShortSchema)
    assert schema.model_dump(mode="json") == {
        "pull_request_id": "pr1",
        "pull_request_name": "Add search",
        "author_id": "u1",
        "status": "OPEN",
    }
