from typing import Annotated

from pydantic import StringConstraints

from core.domain.constraints import (
    PULL_REQUEST_ID_LENGTH,
    PULL_REQUEST_NAME_LENGTH,
    TEAM_NAME_LENGTH,
    USER_ID_LENGTH,
    USERNAME_LENGTH,
)

type UserId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=USER_ID_LENGTH),
]
type TeamName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TEAM_NAME_LENGTH),
]
type Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=USERNAME_LENGTH),
]
type PullRequestId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PULL_REQUEST_ID_LENGTH,
    ),
]
type PullRequestName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PULL_REQUEST_NAME_LENGTH,
    ),
]
