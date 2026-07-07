from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pr_status = postgresql.ENUM("OPEN", "MERGED", name="pr_status")
    pr_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "teams",
        sa.Column("team_name", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("team_name", name="pk_teams"),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=20), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("team_name", sa.String(length=20), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["team_name"],
            ["teams.team_name"],
            name="fk_users_team_name_teams",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
    )
    op.create_index(
        "idx_users_team_active_user_id",
        "users",
        ["team_name", "is_active", "user_id"],
    )
    op.create_table(
        "pull_requests",
        sa.Column("pull_request_id", sa.String(length=20), nullable=False),
        sa.Column("pull_request_name", sa.String(length=100), nullable=False),
        sa.Column("author_id", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "OPEN",
                "MERGED",
                name="pr_status",
                create_type=False,
            ),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'OPEN' AND merged_at IS NULL) OR "
            "(status = 'MERGED' AND merged_at IS NOT NULL)",
            name=op.f("ck_pull_requests_status_merged_at"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.user_id"],
            name="fk_pull_requests_author_id_users",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("pull_request_id", name="pk_pull_requests"),
    )
    op.create_index(
        "idx_pull_requests_author_id",
        "pull_requests",
        ["author_id"],
    )
    op.create_table(
        "pull_request_reviewers",
        sa.Column("pull_request_id", sa.String(length=20), nullable=False),
        sa.Column("reviewer_id", sa.String(length=20), nullable=False),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "slot IN (1, 2)",
            name=op.f("ck_pull_request_reviewers_slot_in_range"),
        ),
        sa.ForeignKeyConstraint(
            ["pull_request_id"],
            ["pull_requests.pull_request_id"],
            name="fk_pull_request_reviewers_pull_request_id_pull_requests",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.user_id"],
            name="fk_pull_request_reviewers_reviewer_id_users",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "pull_request_id",
            "reviewer_id",
            name="pk_pull_request_reviewers",
        ),
        sa.UniqueConstraint(
            "pull_request_id",
            "slot",
            name="uq_pull_request_reviewers_pull_request_id_slot",
        ),
    )
    op.create_index(
        "idx_pull_request_reviewers_reviewer_id_pull_request_id",
        "pull_request_reviewers",
        ["reviewer_id", "pull_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_pull_request_reviewers_reviewer_id_pull_request_id",
        table_name="pull_request_reviewers",
    )
    op.drop_table("pull_request_reviewers")
    op.drop_index("idx_pull_requests_author_id", table_name="pull_requests")
    op.drop_table("pull_requests")
    op.drop_index("idx_users_team_active_user_id", table_name="users")
    op.drop_table("users")
    op.drop_table("teams")

    pr_status = postgresql.ENUM("OPEN", "MERGED", name="pr_status")
    pr_status.drop(op.get_bind(), checkfirst=True)
