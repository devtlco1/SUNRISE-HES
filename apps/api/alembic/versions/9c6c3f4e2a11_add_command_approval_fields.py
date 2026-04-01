"""add command approval fields

Revision ID: 9c6c3f4e2a11
Revises: 1ac97674d941
Create Date: 2026-04-01 18:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9c6c3f4e2a11"
down_revision = "1ac97674d941"
branch_labels = None
depends_on = None


def upgrade() -> None:
    command_approval_status_enum = postgresql.ENUM(
        "not_required",
        "submitted_for_approval",
        "approved",
        "rejected",
        name="command_approval_status",
    )
    command_approval_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "commands",
        sa.Column(
            "approval_status",
            sa.Enum(
                "not_required",
                "submitted_for_approval",
                "approved",
                "rejected",
                name="command_approval_status",
            ),
            server_default="not_required",
            nullable=False,
        ),
    )
    op.add_column("commands", sa.Column("approval_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("commands", sa.Column("approval_reviewed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("commands", sa.Column("approval_notes", sa.Text(), nullable=True))
    op.create_index(
        "ix_commands_approval_status_requested_at",
        "commands",
        ["approval_status", "requested_at"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_commands_approval_reviewed_by_user_id_users"),
        "commands",
        "users",
        ["approval_reviewed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_commands_approval_reviewed_by_user_id_users"), "commands", type_="foreignkey")
    op.drop_index("ix_commands_approval_status_requested_at", table_name="commands")
    op.drop_column("commands", "approval_notes")
    op.drop_column("commands", "approval_reviewed_by_user_id")
    op.drop_column("commands", "approval_reviewed_at")
    op.drop_column("commands", "approval_status")

    command_approval_status_enum = postgresql.ENUM(
        "not_required",
        "submitted_for_approval",
        "approved",
        "rejected",
        name="command_approval_status",
    )
    command_approval_status_enum.drop(op.get_bind(), checkfirst=True)
