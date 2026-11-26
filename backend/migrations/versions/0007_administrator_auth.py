"""Add the local administrator and revocable session storage.

Revision ID: 0007_administrator_auth
Revises: 0006_sender_profiles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_administrator_auth"
down_revision: str | Sequence[str] | None = "0006_sender_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create empty auth tables without creating default credentials."""

    op.create_table(
        "administrators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "administrator_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_administrator_sessions_expires_at", "administrator_sessions", ["expires_at"])


def downgrade() -> None:
    """Remove sessions before deleting administrator credentials."""

    op.drop_index("ix_administrator_sessions_expires_at", table_name="administrator_sessions")
    op.drop_table("administrator_sessions")
    op.drop_table("administrators")
