from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.domain.constraints import (
    PULL_REQUEST_ID_LENGTH,
    PULL_REQUEST_NAME_LENGTH,
    TEAM_NAME_LENGTH,
    USER_ID_LENGTH,
    USERNAME_LENGTH,
)
from core.domain.enums.pull_requests import PRStatus


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class TeamModel(Base):
    __tablename__ = "teams"

    team_name: Mapped[str] = mapped_column(
        String(TEAM_NAME_LENGTH),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    users: Mapped[list[UserModel]] = relationship(back_populates="team")


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "idx_users_team_active_user_id",
            "team_name",
            "is_active",
            "user_id",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(USER_ID_LENGTH),
        primary_key=True,
    )
    username: Mapped[str] = mapped_column(String(USERNAME_LENGTH), nullable=False)
    team_name: Mapped[str] = mapped_column(
        String(TEAM_NAME_LENGTH),
        ForeignKey(
            "teams.team_name",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    team: Mapped[TeamModel] = relationship(back_populates="users")
    authored_pull_requests: Mapped[list[PullRequestModel]] = relationship(
        back_populates="author"
    )
    review_assignments: Mapped[list[PullRequestReviewerModel]] = relationship(
        back_populates="reviewer"
    )


class PullRequestModel(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        CheckConstraint(
            "(status = 'OPEN' AND merged_at IS NULL) OR "
            "(status = 'MERGED' AND merged_at IS NOT NULL)",
            name="status_merged_at",
        ),
        Index("idx_pull_requests_author_id", "author_id"),
    )

    pull_request_id: Mapped[str] = mapped_column(
        String(PULL_REQUEST_ID_LENGTH),
        primary_key=True,
    )
    pull_request_name: Mapped[str] = mapped_column(
        String(PULL_REQUEST_NAME_LENGTH),
        nullable=False,
    )
    author_id: Mapped[str] = mapped_column(
        String(USER_ID_LENGTH),
        ForeignKey(
            "users.user_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[PRStatus] = mapped_column(
        Enum(
            PRStatus,
            name="pr_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=PRStatus.OPEN,
        server_default=PRStatus.OPEN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped[UserModel] = relationship(back_populates="authored_pull_requests")
    reviewers: Mapped[list[PullRequestReviewerModel]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
        order_by="PullRequestReviewerModel.slot",
    )


class PullRequestReviewerModel(Base):
    __tablename__ = "pull_request_reviewers"
    __table_args__ = (
        CheckConstraint("slot IN (1, 2)", name="slot_in_range"),
        UniqueConstraint(
            "pull_request_id",
            "slot",
            name="uq_pull_request_reviewers_pull_request_id_slot",
        ),
        Index(
            "idx_pull_request_reviewers_reviewer_id_pull_request_id",
            "reviewer_id",
            "pull_request_id",
        ),
    )

    pull_request_id: Mapped[str] = mapped_column(
        String(PULL_REQUEST_ID_LENGTH),
        ForeignKey("pull_requests.pull_request_id", ondelete="CASCADE"),
        primary_key=True,
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(USER_ID_LENGTH),
        ForeignKey(
            "users.user_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    pull_request: Mapped[PullRequestModel] = relationship(back_populates="reviewers")
    reviewer: Mapped[UserModel] = relationship(back_populates="review_assignments")
