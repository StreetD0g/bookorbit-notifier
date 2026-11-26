"""Add per-library Discord delivery aggregation settings.

Revision ID: 0005_delivery_modes
Revises: 0004_configuration_templates
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_delivery_modes"
down_revision: str | Sequence[str] | None = "0004_configuration_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Give existing libraries safe single-message defaults without dropping data."""

    with op.batch_alter_table("libraries") as batch:
        batch.add_column(
            sa.Column(
                "delivery_mode",
                sa.Enum("SINGLE", "BATCH", "DAILY_SUMMARY", name="deliverymode", native_enum=False),
                nullable=False,
                server_default="SINGLE",
            )
        )
        batch.add_column(sa.Column("batch_window_seconds", sa.Integer(), nullable=False, server_default="300"))
        batch.add_column(sa.Column("daily_summary_time", sa.String(length=5), nullable=False, server_default="18:00"))
        batch.add_column(sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Berlin"))


def downgrade() -> None:
    """Remove only the aggregation settings, preserving all existing deliveries."""

    with op.batch_alter_table("libraries") as batch:
        batch.drop_column("timezone")
        batch.drop_column("daily_summary_time")
        batch.drop_column("batch_window_seconds")
        batch.drop_column("delivery_mode")
