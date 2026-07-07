from dataclasses import dataclass, field
from datetime import datetime

from core.domain.enums.pull_requests import PRStatus


@dataclass(slots=True, kw_only=True)
class PullRequestShort:
    pull_request_id: str
    pull_request_name: str
    author_id: str
    status: PRStatus


@dataclass(slots=True, kw_only=True)
class PullRequest(PullRequestShort):
    assigned_reviewers: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    merged_at: datetime | None = None


@dataclass(slots=True, kw_only=True)
class PullRequestReviewer:
    pull_request_id: str
    reviewer_id: str
    slot: int
    assigned_at: datetime | None = None
