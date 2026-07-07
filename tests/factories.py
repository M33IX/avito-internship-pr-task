from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from api.v1.teams.schemas import Team as TeamSchema
from api.v1.teams.schemas import TeamMember as TeamMemberSchema
from core.application.use_cases import AddTeamCommand, TeamMemberInput
from core.domain.entities import PullRequest, PullRequestReviewer, TeamMember, User
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.logger import ILogger


@dataclass(slots=True)
class LogRecord:
    level: str
    message: str
    context: dict[str, Any]


@dataclass(slots=True)
class SpyLogger(ILogger):
    records: list[LogRecord] = field(default_factory=list[LogRecord])

    def debug(self, message: str, **context: Any) -> None:
        self.records.append(LogRecord("debug", message, context))

    def info(self, message: str, **context: Any) -> None:
        self.records.append(LogRecord("info", message, context))

    def warning(self, message: str, **context: Any) -> None:
        self.records.append(LogRecord("warning", message, context))

    def error(self, message: str, **context: Any) -> None:
        self.records.append(LogRecord("error", message, context))

    def exception(self, message: str, **context: Any) -> None:
        self.records.append(LogRecord("exception", message, context))


def backend_members_input() -> list[TeamMemberInput]:
    return [
        TeamMemberInput(user_id="u1", username="Author", is_active=True),
        TeamMemberInput(user_id="u2", username="Reviewer Two", is_active=True),
        TeamMemberInput(user_id="u3", username="Reviewer Three", is_active=True),
        TeamMemberInput(user_id="u4", username="Replacement", is_active=True),
        TeamMemberInput(user_id="u5", username="Inactive", is_active=False),
    ]


def backend_team_command(team_name: str = "backend") -> AddTeamCommand:
    return AddTeamCommand(team_name=team_name, members=backend_members_input())


def team_schema(
    team_name: str = "backend",
    members: list[TeamMemberSchema] | None = None,
) -> TeamSchema:
    return TeamSchema(
        team_name=team_name,
        members=members
        or [
            TeamMemberSchema(user_id="u1", username="Author", is_active=True),
            TeamMemberSchema(user_id="u2", username="Reviewer Two", is_active=True),
            TeamMemberSchema(
                user_id="u3",
                username="Reviewer Three",
                is_active=True,
            ),
            TeamMemberSchema(user_id="u4", username="Replacement", is_active=True),
            TeamMemberSchema(user_id="u5", username="Inactive", is_active=False),
        ],
    )


def domain_team_members() -> list[TeamMember]:
    return [
        TeamMember(user_id="u1", username="Author", is_active=True),
        TeamMember(user_id="u2", username="Reviewer Two", is_active=True),
        TeamMember(user_id="u3", username="Reviewer Three", is_active=True),
        TeamMember(user_id="u4", username="Replacement", is_active=True),
        TeamMember(user_id="u5", username="Inactive", is_active=False),
    ]


def domain_user(
    user_id: str = "u1",
    username: str = "Author",
    team_name: str = "backend",
    is_active: bool = True,
) -> User:
    return User(
        user_id=user_id,
        username=username,
        team_name=team_name,
        is_active=is_active,
    )


def domain_pull_request(
    pull_request_id: str = "pr1",
    pull_request_name: str = "Add search",
    author_id: str = "u1",
    status: PRStatus = PRStatus.OPEN,
    assigned_reviewers: list[str] | None = None,
    created_at: datetime | None = None,
    merged_at: datetime | None = None,
) -> PullRequest:
    return PullRequest(
        pull_request_id=pull_request_id,
        pull_request_name=pull_request_name,
        author_id=author_id,
        status=status,
        assigned_reviewers=assigned_reviewers or ["u2", "u3"],
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
        merged_at=merged_at,
    )


def reviewer(
    pull_request_id: str,
    reviewer_id: str,
    slot: int,
) -> PullRequestReviewer:
    return PullRequestReviewer(
        pull_request_id=pull_request_id,
        reviewer_id=reviewer_id,
        slot=slot,
        assigned_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
