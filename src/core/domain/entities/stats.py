from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class AssignmentCount:
    user_id: str
    pull_requests: int


@dataclass(slots=True, kw_only=True)
class PullRequestReviewersCount:
    pull_request_id: str
    reviewers: int


@dataclass(slots=True, kw_only=True)
class ServiceStats:
    teams: int
    users: int
    active_users: int
    inactive_users: int
    pull_requests: int
    open_pull_requests: int
    merged_pull_requests: int
    assignments: int
    assignments_by_user: list[AssignmentCount]
    reviewers_by_pull_request: list[PullRequestReviewersCount]
