"""Add delayed metadata refresh and stale-delivery recovery state.

Revision ID: 0002_metadata_wait
Revises: 0001_core_outbox
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_metadata_wait"
down_revision: str | Sequence[str] | None = "0001_core_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable event timestamps so existing installations migrate without data loss."""

    with op.batch_alter_table("libraries") as batch:
        batch.add_column(sa.Column("metadata_delay_seconds", sa.Integer(), nullable=False, server_default="120"))
        batch.add_column(sa.Column("metadata_max_wait_seconds", sa.Integer(), nullable=False, server_default="1800"))
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("metadata_not_before_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("metadata_deadline_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("metadata_attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("metadata_last_error", sa.Text(), nullable=True))
    op.create_index("ix_events_metadata_not_before_at", "events", ["metadata_not_before_at"])
    with op.batch_alter_table("notification_queue") as batch:
        batch.add_column(sa.Column("sending_started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notification_queue_sending_started_at", "notification_queue", ["sending_started_at"])


def downgrade() -> None:
    """Reverse added columns in batch mode for SQLite compatibility."""

    op.drop_index("ix_notification_queue_sending_started_at", table_name="notification_queue")
    with op.batch_alter_table("notification_queue") as batch:
        batch.drop_column("sending_started_at")
    op.drop_index("ix_events_metadata_not_before_at", table_name="events")
    with op.batch_alter_table("events") as batch:
        batch.drop_column("metadata_last_error")
        batch.drop_column("metadata_attempt_count")
        batch.drop_column("metadata_deadline_at")
        batch.drop_column("metadata_not_before_at")
    with op.batch_alter_table("libraries") as batch:
        batch.drop_column("metadata_max_wait_seconds")
        batch.drop_column("metadata_delay_seconds")
