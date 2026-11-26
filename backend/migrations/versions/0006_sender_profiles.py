"""Add independent per-scope Discord sender profiles.

Revision ID: 0006_sender_profiles
Revises: 0005_delivery_modes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_sender_profiles"
down_revision: str | Sequence[str] | None = "0005_delivery_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a separate configuration table without altering existing destinations."""

    op.create_table(
        "sender_profile_configs",
        sa.Column("scope_key", sa.String(64), primary_key=True),
        sa.Column("username_choice", sa.String(16), nullable=False),
        sa.Column("username_value", sa.String(80), nullable=True),
        sa.Column("avatar_choice", sa.String(16), nullable=False),
        sa.Column("avatar_value", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    """Remove profile configuration without affecting webhooks or queue history."""

    op.drop_table("sender_profile_configs")
