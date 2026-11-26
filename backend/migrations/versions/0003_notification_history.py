"""Create immutable per-target notification attempt history.

Revision ID: 0003_notification_history
Revises: 0002_metadata_wait
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_notification_history"
down_revision: str | Sequence[str] | None = "0002_metadata_wait"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep prior message IDs/errors when a manual retry later reuses the queue row."""

    op.create_table(
        "notification_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("queue_item_id", sa.Integer(), sa.ForeignKey("notification_queue.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("WAITING_FOR_METADATA", "READY", "QUEUED", "SENDING", "SENT", "RETRY", "FAILED", "SKIPPED", native_enum=False),
            nullable=False,
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("discord_message_id", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_notification_history_queue_item_id", "notification_history", ["queue_item_id"])
    op.create_index("ix_notification_history_queue_attempted", "notification_history", ["queue_item_id", "attempted_at"])


def downgrade() -> None:
    """Remove audit rows only when rolling the schema back deliberately."""

    op.drop_index("ix_notification_history_queue_attempted", table_name="notification_history")
    op.drop_index("ix_notification_history_queue_item_id", table_name="notification_history")
    op.drop_table("notification_history")
