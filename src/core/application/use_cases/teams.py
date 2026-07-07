from dataclasses import dataclass

from core.domain.entities import PullRequest, Team, TeamMember
from core.domain.value_objects import PullRequestReviewerReplacement
from core.exceptions import (
    NoReviewerCandidateError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
)
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


@dataclass(slots=True, kw_only=True)
class TeamMemberInput:
    user_id: str
    username: str
    is_active: bool


@dataclass(slots=True, kw_only=True)
class AddTeamCommand:
    team_name: str
    members: list[TeamMemberInput]


@dataclass(slots=True, kw_only=True)
class DeactivateTeamCommand:
    team_name: str
    replacement_team_name: str


@dataclass(slots=True, kw_only=True)
class DeactivateTeamResult:
    team: Team
    reassignments: list[PullRequestReviewerReplacement]


async def get_team(
    team_name: str,
    uow: IUnitOfWork,
    logger: ILogger,
) -> Team:
    team = await uow.teams.get_by_name(team_name)
    if team is None:
        logger.warning("team not found", team_name=team_name)
        raise TeamNotFoundError("resource not found")

    return team


async def add_team(
    command: AddTeamCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> Team:
    if await uow.teams.exists(command.team_name):
        logger.warning("team already exists", team_name=command.team_name)
        raise TeamAlreadyExistsError("team_name already exists")

    await uow.teams.create(command.team_name)
    await uow.users.upsert_many(
        team_name=command.team_name,
        users=[
            TeamMember(
                user_id=member.user_id,
                username=member.username,
                is_active=member.is_active,
            )
            for member in command.members
        ],
    )
    await uow.commit()

    members = [
        TeamMember(
            user_id=member.user_id,
            username=member.username,
            is_active=member.is_active,
        )
        for member in command.members
    ]
    members.sort(key=lambda member: member.user_id)
    created_team = Team(
        team_name=command.team_name,
        members=members,
    )

    logger.info(
        "team created",
        team_name=created_team.team_name,
        members_count=len(created_team.members),
    )
    return created_team


async def deactivate_team(
    command: DeactivateTeamCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> DeactivateTeamResult:
    team = await uow.teams.get_by_name(command.team_name)
    if team is None:
        logger.warning("team not found", team_name=command.team_name)
        raise TeamNotFoundError("resource not found")

    if not await uow.teams.exists(command.replacement_team_name):
        logger.warning(
            "replacement team not found",
            team_name=command.team_name,
            replacement_team_name=command.replacement_team_name,
        )
        raise TeamNotFoundError("resource not found")

    team_user_ids = {member.user_id for member in team.members}
    open_pull_requests = await uow.pull_requests.list_open_by_reviewer_ids(
        reviewer_ids=team_user_ids,
        for_update=True,
    )
    replacement_candidates = await uow.users.list_active_by_team(
        team_name=command.replacement_team_name,
        exclude_user_ids=team_user_ids,
    )
    reassignments = _plan_team_reviewer_replacements(
        pull_requests=open_pull_requests,
        team_user_ids=team_user_ids,
        candidate_ids=[candidate.user_id for candidate in replacement_candidates],
    )

    await uow.pull_request_reviewers.replace_reviewers(reassignments)
    await uow.users.deactivate_by_team(command.team_name)
    await uow.commit()

    updated_team = Team(
        team_name=team.team_name,
        members=[
            TeamMember(
                user_id=member.user_id,
                username=member.username,
                is_active=False,
            )
            for member in team.members
        ],
    )

    logger.info(
        "team deactivated",
        team_name=command.team_name,
        replacement_team_name=command.replacement_team_name,
        affected_users=len(team_user_ids),
        reassignments_count=len(reassignments),
    )
    return DeactivateTeamResult(
        team=updated_team,
        reassignments=reassignments,
    )


def _plan_team_reviewer_replacements(
    *,
    pull_requests: list[PullRequest],
    team_user_ids: set[str],
    candidate_ids: list[str],
) -> list[PullRequestReviewerReplacement]:
    replacements: list[PullRequestReviewerReplacement] = []
    for pull_request in pull_requests:
        assigned_reviewer_ids = set(pull_request.assigned_reviewers)
        for old_user_id in pull_request.assigned_reviewers:
            if old_user_id not in team_user_ids:
                continue

            excluded_user_ids = {
                pull_request.author_id,
                *team_user_ids,
                *assigned_reviewer_ids,
            }
            new_user_id = next(
                (
                    candidate_id
                    for candidate_id in candidate_ids
                    if candidate_id not in excluded_user_ids
                ),
                None,
            )
            if new_user_id is None:
                raise NoReviewerCandidateError(
                    "no active replacement candidate in team"
                )

            replacements.append(
                PullRequestReviewerReplacement(
                    pull_request_id=pull_request.pull_request_id,
                    old_user_id=old_user_id,
                    new_user_id=new_user_id,
                )
            )
            assigned_reviewer_ids.discard(old_user_id)
            assigned_reviewer_ids.add(new_user_id)

    return replacements
