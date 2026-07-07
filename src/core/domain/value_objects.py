from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class PullRequestReviewerReplacement:
    pull_request_id: str
    old_user_id: str
    new_user_id: str
