from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from core.domain.constraints import TEAM_NAME_LENGTH, USER_ID_LENGTH

pytestmark = pytest.mark.e2e


def team_payload(
    team_name: str = "backend",
    members: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "team_name": team_name,
        "members": list(members)
        if members is not None
        else [
            {"user_id": "u1", "username": "Author", "is_active": True},
            {"user_id": "u2", "username": "Reviewer Two", "is_active": True},
            {"user_id": "u3", "username": "Reviewer Three", "is_active": True},
            {"user_id": "u4", "username": "Replacement", "is_active": True},
            {"user_id": "u5", "username": "Inactive", "is_active": False},
        ],
    }


async def create_team(
    api_client: httpx.AsyncClient,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await api_client.post("/team/add", json=payload or team_payload())
    assert response.status_code == 201
    return response.json()


async def create_pr(
    api_client: httpx.AsyncClient,
    pull_request_id: str = "pr1",
    author_id: str = "u1",
) -> dict[str, Any]:
    response = await api_client.post(
        "/pullRequest/create",
        json={
            "pull_request_id": pull_request_id,
            "pull_request_name": "Add search",
            "author_id": author_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def assert_error(
    response: httpx.Response,
    *,
    status_code: int,
    code: str,
    message: str | None = None,
) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert payload["error"]["code"] == code
    if message is not None:
        assert payload["error"]["message"] == message


@pytest.mark.anyio
async def test_full_happy_path(api_client: httpx.AsyncClient) -> None:
    created_team = await create_team(api_client)
    assert created_team["team"]["team_name"] == "backend"

    team = await api_client.get("/team/get", params={"team_name": "backend"})
    assert team.status_code == 200
    assert [member["user_id"] for member in team.json()["members"]] == [
        "u1",
        "u2",
        "u3",
        "u4",
        "u5",
    ]

    created_pr = await create_pr(api_client)
    pr = created_pr["pr"]
    assert pr["status"] == "OPEN"
    assert len(pr["assigned_reviewers"]) == 2
    assert "u1" not in pr["assigned_reviewers"]
    assert "u5" not in pr["assigned_reviewers"]
    assert "createdAt" in pr
    assert "mergedAt" in pr

    old_reviewer = pr["assigned_reviewers"][0]
    reviews = await api_client.get(
        "/users/getReview",
        params={"user_id": old_reviewer},
    )
    assert reviews.status_code == 200
    assert [item["pull_request_id"] for item in reviews.json()["pull_requests"]] == [
        "pr1"
    ]

    reassigned = await api_client.post(
        "/pullRequest/reassign",
        json={"pull_request_id": "pr1", "old_user_id": old_reviewer},
    )
    assert reassigned.status_code == 200
    reassigned_payload = reassigned.json()
    assert reassigned_payload["replaced_by"] not in {old_reviewer, "u1", "u5"}
    assert old_reviewer not in reassigned_payload["pr"]["assigned_reviewers"]
    assert len(reassigned_payload["pr"]["assigned_reviewers"]) == 2

    replacement_reviews = await api_client.get(
        "/users/getReview",
        params={"user_id": reassigned_payload["replaced_by"]},
    )
    assert replacement_reviews.status_code == 200
    assert replacement_reviews.json()["pull_requests"][0]["pull_request_id"] == "pr1"

    first_merge = await api_client.post(
        "/pullRequest/merge",
        json={"pull_request_id": "pr1"},
    )
    second_merge = await api_client.post(
        "/pullRequest/merge",
        json={"pull_request_id": "pr1"},
    )
    assert first_merge.status_code == 200
    assert second_merge.status_code == 200
    assert first_merge.json()["pr"]["status"] == "MERGED"
    assert second_merge.json()["pr"]["status"] == "MERGED"
    assert first_merge.json()["pr"]["mergedAt"] == second_merge.json()["pr"]["mergedAt"]


@pytest.mark.anyio
async def test_inactive_user_is_not_assigned_to_new_pr(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(
        api_client,
        team_payload(
            members=[
                {"user_id": "u1", "username": "Author", "is_active": True},
                {"user_id": "u2", "username": "Reviewer Two", "is_active": True},
                {"user_id": "u3", "username": "Reviewer Three", "is_active": True},
            ]
        ),
    )

    activity = await api_client.post(
        "/users/setIsActive",
        json={"user_id": "u2", "is_active": False},
    )
    assert activity.status_code == 200
    assert activity.json()["user"]["is_active"] is False

    created_pr = await create_pr(api_client)

    assert created_pr["pr"]["assigned_reviewers"] == ["u3"]


@pytest.mark.anyio
async def test_duplicate_team_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(api_client)

    response = await api_client.post("/team/add", json=team_payload())

    assert_error(
        response,
        status_code=400,
        code="TEAM_EXISTS",
        message="team_name already exists",
    )


@pytest.mark.anyio
async def test_missing_team_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/team/get", params={"team_name": "missing"})

    assert_error(response, status_code=404, code="NOT_FOUND")


@pytest.mark.anyio
async def test_missing_author_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/pullRequest/create",
        json={
            "pull_request_id": "pr1",
            "pull_request_name": "Missing author",
            "author_id": "missing",
        },
    )

    assert_error(response, status_code=404, code="NOT_FOUND")


@pytest.mark.anyio
async def test_duplicate_pr_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(api_client)
    await create_pr(api_client)

    response = await api_client.post(
        "/pullRequest/create",
        json={
            "pull_request_id": "pr1",
            "pull_request_name": "Duplicate",
            "author_id": "u1",
        },
    )

    assert_error(
        response,
        status_code=409,
        code="PR_EXISTS",
        message="PR id already exists",
    )


@pytest.mark.anyio
async def test_reassign_merged_pr_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(api_client)
    created_pr = await create_pr(api_client)
    old_reviewer = created_pr["pr"]["assigned_reviewers"][0]
    await api_client.post("/pullRequest/merge", json={"pull_request_id": "pr1"})

    response = await api_client.post(
        "/pullRequest/reassign",
        json={"pull_request_id": "pr1", "old_user_id": old_reviewer},
    )

    assert_error(
        response,
        status_code=409,
        code="PR_MERGED",
        message="cannot reassign on merged PR",
    )


@pytest.mark.anyio
async def test_reassign_not_assigned_user_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(api_client)
    created_pr = await create_pr(api_client)
    active_reviewers = {"u2", "u3", "u4"}
    not_assigned = next(
        user_id
        for user_id in active_reviewers
        if user_id not in created_pr["pr"]["assigned_reviewers"]
    )

    response = await api_client.post(
        "/pullRequest/reassign",
        json={"pull_request_id": "pr1", "old_user_id": not_assigned},
    )

    assert_error(
        response,
        status_code=409,
        code="NOT_ASSIGNED",
        message="reviewer is not assigned to this PR",
    )


@pytest.mark.anyio
async def test_reassign_without_candidate_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    await create_team(
        api_client,
        team_payload(
            team_name="pair",
            members=[
                {"user_id": "a1", "username": "Author", "is_active": True},
                {"user_id": "r1", "username": "Reviewer", "is_active": True},
            ],
        ),
    )
    created_pr = await create_pr(api_client, author_id="a1")

    response = await api_client.post(
        "/pullRequest/reassign",
        json={
            "pull_request_id": "pr1",
            "old_user_id": created_pr["pr"]["assigned_reviewers"][0],
        },
    )

    assert_error(
        response,
        status_code=409,
        code="NO_CANDIDATE",
        message="no active replacement candidate in team",
    )


@pytest.mark.anyio
async def test_missing_user_activity_update_returns_contract_error(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/users/setIsActive",
        json={"user_id": "missing", "is_active": False},
    )

    assert_error(response, status_code=404, code="NOT_FOUND")


@pytest.mark.anyio
async def test_validation_error_for_missing_required_field(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/pullRequest/create",
        json={"pull_request_id": "pr1", "pull_request_name": "Invalid"},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_validation_error_for_too_long_body_value(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/team/add",
        json=team_payload(team_name="x" * (TEAM_NAME_LENGTH + 1)),
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_validation_error_for_too_long_query_value(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/users/getReview",
        params={"user_id": "x" * (USER_ID_LENGTH + 1)},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_openapi_contains_contract_paths(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/team/add" in paths
    assert "/team/get" in paths
    assert "/users/setIsActive" in paths
    assert "/users/getReview" in paths
    assert "/pullRequest/create" in paths
    assert "/pullRequest/reassign" in paths
    assert "/pullRequest/merge" in paths
