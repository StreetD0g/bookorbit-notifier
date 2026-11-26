"""Persistent state separated into source inventory, detected events, and delivery work."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    """Create timezone-aware UTC timestamps consistently across the persistence layer."""

    return datetime.now(UTC)


class EventType(StrEnum):
    """Extensible source event categories; only BOOK_ADDED is published in the MVP."""

    BOOK_ADDED = "BOOK_ADDED"
    BOOK_REMOVED = "BOOK_REMOVED"
    BOOK_UPDATED = "BOOK_UPDATED"
    BOOK_FORMAT_ADDED = "BOOK_FORMAT_ADDED"
    BOOK_MOVED = "BOOK_MOVED"


class EventStatus(StrEnum):
    """Lifecycle of a source event before all destination work has completed."""

    DETECTED = "DETECTED"
    WAITING_FOR_METADATA = "WAITING_FOR_METADATA"
    READY = "READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class QueueStatus(StrEnum):
    """Per-webhook delivery state; a destination never shares another target's result."""

    WAITING_FOR_METADATA = "WAITING_FOR_METADATA"
    READY = "READY"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    RETRY = "RETRY"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ScanStatus(StrEnum):
    """A scan can be useful but incomplete; incomplete scans never imply removal."""

    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Server(Base):
    """One configured BookOrbit instance; its encrypted API key is never serialized."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    base_url: Mapped[str] = mapped_column(String(2048))
    public_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    libraries: Mapped[list[Library]] = relationship(back_populates="server", cascade="all, delete-orphan")
    books: Mapped[list[Book]] = relationship(back_populates="server", cascade="all, delete-orphan")


class Library(Base):
    """A BookOrbit library with its own monitor and routing configuration."""

    __tablename__ = "libraries"
    __table_args__ = (UniqueConstraint("server_id", "bookorbit_library_id", name="uq_library_source_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    bookorbit_library_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    monitored: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_delay_seconds: Mapped[int] = mapped_column(Integer, default=120, server_default="120")
    metadata_max_wait_seconds: Mapped[int] = mapped_column(Integer, default=1800, server_default="1800")
    baseline_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    server: Mapped[Server] = relationship(back_populates="libraries")
    books: Mapped[list[Book]] = relationship(back_populates="library")
    webhooks: Mapped[list[Webhook]] = relationship(secondary="library_webhooks", back_populates="libraries")


class Book(Base):
    """One logical BookOrbit book, identified only by its source server and numeric ID."""

    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("server_id", "bookorbit_book_id", name="uq_book_source_identity"),
        Index("ix_books_library_seen", "library_id", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="RESTRICT"), index=True)
    bookorbit_book_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    authors_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_added_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    server: Mapped[Server] = relationship(back_populates="books")
    library: Mapped[Library] = relationship(back_populates="books")
    events: Mapped[list[Event]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Event(Base):
    """Durable evidence that a source change was detected before delivery begins."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("book_id", "event_type", name="uq_event_book_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="RESTRICT"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus, native_enum=False), default=EventStatus.DETECTED)
    metadata_not_before_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    metadata_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped[Book] = relationship(back_populates="events")
    deliveries: Mapped[list[NotificationQueueItem]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Webhook(Base):
    """Discord destination; URL encryption is deliberate even though messages are outbound."""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    url_encrypted: Mapped[str] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    libraries: Mapped[list[Library]] = relationship(secondary="library_webhooks", back_populates="webhooks")
    deliveries: Mapped[list[NotificationQueueItem]] = relationship(back_populates="webhook")


class LibraryWebhook(Base):
    """Route a monitored library to zero or more independent Discord targets."""

    __tablename__ = "library_webhooks"

    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotificationQueueItem(Base):
    """One event-to-webhook attempt stream; success at one target does not affect another."""

    __tablename__ = "notification_queue"
    __table_args__ = (
        UniqueConstraint("event_id", "webhook_id", name="uq_delivery_event_webhook"),
        Index("ix_notification_queue_ready", "status", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus, native_enum=False), default=QueueStatus.WAITING_FOR_METADATA)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discord_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    event: Mapped[Event] = relationship(back_populates="deliveries")
    webhook: Mapped[Webhook] = relationship(back_populates="deliveries")


class ScanHistory(Base):
    """An auditable scan outcome; incomplete inventory never drives deletion logic."""

    __tablename__ = "scan_history"
    __table_args__ = (Index("ix_scan_history_library_started", "library_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, native_enum=False))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    books_seen: Mapped[int] = mapped_column(Integer, default=0)
    books_added: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
