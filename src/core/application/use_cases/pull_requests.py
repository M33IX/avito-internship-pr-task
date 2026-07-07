import random
from dataclasses import dataclass

from core.domain.entities import PullRequest
from core.domain.enums.pull_requests import PRStatus
from core.exceptions import (
    NoReviewerCandidateError,
    PullRequestAlreadyExistsError,
    PullRequestMergedError,
    PullRequestNotFoundError,
    ReviewerNotAssignedError,
    UserNotFoundError,
)
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


@dataclass(slots=True, kw_only=True)
class CreatePullRequestCommand:
    pull_request_id: str
    pull_request_name: str
    author_id: str


@dataclass(slots=True, kw_only=True)
class MergePullRequestCommand:
    pull_request_id: str


@dataclass(slots=True, kw_only=True)
class ReassignPullRequestReviewerCommand:
    pull_request_id: str
    old_user_id: str


@dataclass(slots=True, kw_only=True)
class ReassignPullRequestReviewerResult:
    pull_request: PullRequest
    replaced_by: str


async def create_pull_request(
    command: CreatePullRequestCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> PullRequest:
    pull_request = await uow.pull_requests.create_if_author_exists(
        pull_request_id=command.pull_request_id,
        pull_request_name=command.pull_request_name,
        author_id=command.author_id,
    )
    if pull_request is None and await uow.pull_requests.exists(
        command.pull_request_id
    ):
        logger.warning(
            "pull request already exists",
            pull_request_id=command.pull_request_id,
        )
        raise PullRequestAlreadyExistsError("PR id already exists")
    if pull_request is None:
        logger.warning(
            "pull request author not found",
            author_id=command.author_id,
        )
        raise UserNotFoundError("resource not found")

    author_with_candidates = await uow.users.get_with_active_teammates(
        command.author_id
    )
    if author_with_candidates is None:
        logger.warning(
            "pull request author not found",
            author_id=command.author_id,
        )
        raise UserNotFoundError("resource not found")

    _, candidates = author_with_candidates
    reviewers = random.sample(
        candidates,
        k=min(2, len(candidates)),
    )
    reviewer_ids = [reviewer.user_id for reviewer in reviewers]

    await uow.pull_request_reviewers.add_reviewers(
        pull_request_id=pull_request.pull_request_id,
        reviewer_ids=reviewer_ids,
    )
    await uow.commit()

    created_pull_request = PullRequest(
        pull_request_id=pull_request.pull_request_id,
        pull_request_name=pull_request.pull_request_name,
        author_id=pull_request.author_id,
        status=pull_request.status,
        assigned_reviewers=reviewer_ids,
        created_at=pull_request.created_at,
        merged_at=pull_request.merged_at,
    )

    logger.info(
        "pull request created",
        pull_request_id=created_pull_request.pull_request_id,
        author_id=created_pull_request.author_id,
        reviewers_count=len(created_pull_request.assigned_reviewers),
    )
    return created_pull_request


async def merge_pull_request(
    command: MergePullRequestCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> PullRequest:
    pull_request = await uow.pull_requests.mark_merged(command.pull_request_id)
    if pull_request is None:
        logger.warning(
            "pull request not found",
            pull_request_id=command.pull_request_id,
        )
        raise PullRequestNotFoundError("resource not found")

    await uow.commit()
    logger.info(
        "pull request merged",
        pull_request_id=pull_request.pull_request_id,
        status=pull_request.status,
    )
    return pull_request


async def reassign_pull_request_reviewer(
    command: ReassignPullRequestReviewerCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> ReassignPullRequestReviewerResult:
    pull_request = await uow.pull_requests.get_by_id_for_update(command.pull_request_id)
    if pull_request is None:
        logger.warning(
            "pull request not found",
            pull_request_id=command.pull_request_id,
        )
        raise PullRequestNotFoundError("resource not found")

    old_reviewer = await uow.users.get_by_id(command.old_user_id)
    if old_reviewer is None:
        logger.warning(
            "old reviewer not found",
            pull_request_id=command.pull_request_id,
            old_user_id=command.old_user_id,
        )
        raise UserNotFoundError("resource not found")

    if pull_request.status == PRStatus.MERGED:
        logger.warning(
            "cannot reassign merged pull request",
            pull_request_id=command.pull_request_id,
        )
        raise PullRequestMergedError("cannot reassign on merged PR")

    assigned_reviewer_ids = pull_request.assigned_reviewers
    if command.old_user_id not in assigned_reviewer_ids:
        logger.warning(
            "reviewer is not assigned",
            pull_request_id=command.pull_request_id,
            old_user_id=command.old_user_id,
        )
        raise ReviewerNotAssignedError("reviewer is not assigned to this PR")

    excluded_user_ids = {
        pull_request.author_id,
        command.old_user_id,
        *assigned_reviewer_ids,
    }
    candidates = await uow.users.list_active_by_team(
        team_name=old_reviewer.team_name,
        exclude_user_ids=excluded_user_ids,
    )
    if not candidates:
        logger.warning(
            "no replacement candidate",
            pull_request_id=command.pull_request_id,
            old_user_id=command.old_user_id,
        )
        raise NoReviewerCandidateError("no active replacement candidate in team")

    new_reviewer = random.choice(candidates)
    await uow.pull_request_reviewers.replace_reviewer(
        pull_request_id=command.pull_request_id,
        old_user_id=command.old_user_id,
        new_user_id=new_reviewer.user_id,
    )
    await uow.commit()

    updated_pull_request = PullRequest(
        pull_request_id=pull_request.pull_request_id,
        pull_request_name=pull_request.pull_request_name,
        author_id=pull_request.author_id,
        status=pull_request.status,
        assigned_reviewers=[
            new_reviewer.user_id if user_id == command.old_user_id else user_id
            for user_id in assigned_reviewer_ids
        ],
        created_at=pull_request.created_at,
        merged_at=pull_request.merged_at,
    )

    logger.info(
        "pull request reviewer reassigned",
        pull_request_id=command.pull_request_id,
        old_user_id=command.old_user_id,
        new_user_id=new_reviewer.user_id,
    )
    return ReassignPullRequestReviewerResult(
        pull_request=updated_pull_request,
        replaced_by=new_reviewer.user_id,
    )
