from __future__ import annotations

import json

import pytest

from api.v1.errors import DOMAIN_ERROR_MAPPING, ErrorCode, app_error_handler
from core.exceptions import (
    AppError,
    NoReviewerCandidateError,
    PullRequestAlreadyExistsError,
    PullRequestMergedError,
    PullRequestNotFoundError,
    ReviewerNotAssignedError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
    UserNotFoundError,
)

pytestmark = pytest.mark.unit


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("exc_type", "expected_status", "expected_code"),
    [
        (TeamAlreadyExistsError, 400, ErrorCode.TEAM_EXISTS),
        (TeamNotFoundError, 404, ErrorCode.NOT_FOUND),
        (UserNotFoundError, 404, ErrorCode.NOT_FOUND),
        (PullRequestAlreadyExistsError, 409, ErrorCode.PR_EXISTS),
        (PullRequestNotFoundError, 404, ErrorCode.NOT_FOUND),
        (PullRequestMergedError, 409, ErrorCode.PR_MERGED),
        (ReviewerNotAssignedError, 409, ErrorCode.NOT_ASSIGNED),
        (NoReviewerCandidateError, 409, ErrorCode.NO_CANDIDATE),
    ],
)
async def test_domain_errors_are_mapped_to_contract_responses(
    exc_type: type[AppError],
    expected_status: int,
    expected_code: ErrorCode,
) -> None:
    assert DOMAIN_ERROR_MAPPING[exc_type] == (expected_status, expected_code)

    response = await app_error_handler(None, exc_type("expected message"))  # type: ignore[arg-type]
    payload = json.loads(bytes(response.body))

    assert response.status_code == expected_status
    assert payload == {
        "error": {
            "code": expected_code,
            "message": "expected message",
        }
    }
