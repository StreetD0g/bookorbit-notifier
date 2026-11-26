"""Create the notifier's source inventory and independent delivery outbox.

Revision ID: 0001_core_outbox
Revises:
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_core_outbox"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create core records before any scheduler or user interface is introduced."""

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scan_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "libraries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bookorbit_library_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("monitored", sa.Boolean(), nullable=False),
        sa.Column("baseline_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("server_id", "bookorbit_library_id", name="uq_library_source_identity"),
    )
    op.create_index("ix_libraries_server_id", "libraries", ["server_id"])
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("url_encrypted", sa.Text(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=True),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "library_webhooks",
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bookorbit_book_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("authors_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_added_at", sa.String(length=64), nullable=True),
        sa.Column("source_updated_at", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("server_id", "bookorbit_book_id", name="uq_book_source_identity"),
    )
    op.create_index("ix_books_server_id", "books", ["server_id"])
    op.create_index("ix_books_library_id", "books", ["library_id"])
    op.create_index("ix_books_library_seen", "books", ["library_id", "last_seen_at"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("BOOK_ADDED", "BOOK_REMOVED", "BOOK_UPDATED", "BOOK_FORMAT_ADDED", "BOOK_MOVED", native_enum=False),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DETECTED", "WAITING_FOR_METADATA", "READY", "COMPLETED", "FAILED", "SKIPPED", native_enum=False),
            nullable=False,
        ),
        sa.UniqueConstraint("book_id", "event_type", name="uq_event_book_type"),
    )
    op.create_index("ix_events_server_id", "events", ["server_id"])
    op.create_index("ix_events_library_id", "events", ["library_id"])
    op.create_index("ix_events_book_id", "events", ["book_id"])
    op.create_table(
        "notification_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("WAITING_FOR_METADATA", "READY", "QUEUED", "SENDING", "SENT", "RETRY", "FAILED", "SKIPPED", native_enum=False),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discord_message_id", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("event_id", "webhook_id", name="uq_delivery_event_webhook"),
    )
    op.create_index("ix_notification_queue_event_id", "notification_queue", ["event_id"])
    op.create_index("ix_notification_queue_webhook_id", "notification_queue", ["webhook_id"])
    op.create_index("ix_notification_queue_ready", "notification_queue", ["status", "next_retry_at"])
    op.create_table(
        "scan_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("SUCCEEDED", "PARTIAL", "FAILED", native_enum=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("books_seen", sa.Integer(), nullable=False),
        sa.Column("books_added", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_scan_history_server_id", "scan_history", ["server_id"])
    op.create_index("ix_scan_history_library_id", "scan_history", ["library_id"])
    op.create_index("ix_scan_history_library_started", "scan_history", ["library_id", "started_at"])


def downgrade() -> None:
    """Remove the schema in dependency order for development-only rollback."""

    op.drop_index("ix_scan_history_library_started", table_name="scan_history")
    op.drop_index("ix_scan_history_library_id", table_name="scan_history")
    op.drop_index("ix_scan_history_server_id", table_name="scan_history")
    op.drop_table("scan_history")
    op.drop_index("ix_notification_queue_ready", table_name="notification_queue")
    op.drop_index("ix_notification_queue_webhook_id", table_name="notification_queue")
    op.drop_index("ix_notification_queue_event_id", table_name="notification_queue")
    op.drop_table("notification_queue")
    op.drop_index("ix_events_book_id", table_name="events")
    op.drop_index("ix_events_library_id", table_name="events")
    op.drop_index("ix_events_server_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_books_library_seen", table_name="books")
    op.drop_index("ix_books_library_id", table_name="books")
    op.drop_index("ix_books_server_id", table_name="books")
    op.drop_table("books")
    op.drop_table("library_webhooks")
    op.drop_table("webhooks")
    op.drop_index("ix_libraries_server_id", table_name="libraries")
    op.drop_table("libraries")
    op.drop_table("servers")
