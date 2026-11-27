"""Administrator-facing notification status and explicit retry operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Book, Event, EventStatus, Library, NotificationHistory, NotificationQueueItem, QueueStatus, Server, Webhook

type SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class NotificationStatusSummary:
    """Aggregated delivery state for a dashboard without destination secrets."""

    waiting_for_metadata: int
    ready: int
    queued: int
    sending: int
    retry: int
    sent: int
    failed: int
    skipped: int


@dataclass(frozen=True, slots=True)
class NotificationHistoryEntry:
    """Safe audit record for one prior delivery result or manual retry request."""

    id: int
    queue_item_id: int
    status: QueueStatus
    attempted_at: datetime
    error: str | None
    discord_message_id: str | None


@dataclass(frozen=True, slots=True)
class NotificationListEntry:
    """One safe destination record for the administrator history list."""

    id: int
    book_title: str | None
    server_name: str
    library_name: str
    webhook_name: str
    detected_at: datetime
    sent_at: datetime | None
    next_retry_at: datetime | None
    sending_started_at: datetime | None
    status: QueueStatus
    attempt_count: int
    last_error: str | None
    discord_message_id: str | None


class NotificationAdministrationService:
    """Persistent status reads and deliberate retry transitions for a future authenticated API."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def summary(self) -> NotificationStatusSummary:
        """Return counts for every queue status, including zero-count states."""

        with self._session_factory() as session:
            rows = session.execute(
                select(NotificationQueueItem.status, func.count(NotificationQueueItem.id)).group_by(NotificationQueueItem.status)
            ).all()
        counts = {status: int(count) for status, count in rows}
        return NotificationStatusSummary(
            waiting_for_metadata=counts.get(QueueStatus.WAITING_FOR_METADATA, 0),
            ready=counts.get(QueueStatus.READY, 0),
            queued=counts.get(QueueStatus.QUEUED, 0),
            sending=counts.get(QueueStatus.SENDING, 0),
            retry=counts.get(QueueStatus.RETRY, 0),
            sent=counts.get(QueueStatus.SENT, 0),
            failed=counts.get(QueueStatus.FAILED, 0),
            skipped=counts.get(QueueStatus.SKIPPED, 0),
        )

    def history(self, queue_item_id: int) -> list[NotificationHistoryEntry]:
        """Return immutable delivery history in chronological order for one target."""

        with self._session_factory() as session:
            rows = session.scalars(
                select(NotificationHistory)
                .where(NotificationHistory.queue_item_id == queue_item_id)
                # IDs are append-only and avoid SQLite timezone serialization affecting ties.
                .order_by(NotificationHistory.id)
            ).all()
        return [
            NotificationHistoryEntry(
                id=row.id,
                queue_item_id=row.queue_item_id,
                status=row.status,
                attempted_at=row.attempted_at,
                error=row.error,
                discord_message_id=row.discord_message_id,
            )
            for row in rows
        ]

    def list_deliveries(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: QueueStatus | None = None,
        server_id: int | None = None,
        library_id: int | None = None,
    ) -> list[NotificationListEntry]:
        """Page newest queue records without serializing source or webhook credentials."""

        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid notification pagination")
        with self._session_factory() as session:
            query = (
                select(NotificationQueueItem, Book.title, Server.name, Library.name, Webhook.name, Event.detected_at)
                .join(Event, NotificationQueueItem.event_id == Event.id)
                .join(Book, Event.book_id == Book.id)
                .join(Server, Event.server_id == Server.id)
                .join(Library, Event.library_id == Library.id)
                .join(Webhook, NotificationQueueItem.webhook_id == Webhook.id)
            )
            if status is not None:
                query = query.where(NotificationQueueItem.status == status)
            if server_id is not None:
                query = query.where(Event.server_id == server_id)
            if library_id is not None:
                query = query.where(Event.library_id == library_id)
            rows = session.execute(query.order_by(NotificationQueueItem.id.desc()).limit(limit).offset(offset)).all()
            return [
                NotificationListEntry(
                    id=item.id,
                    book_title=title,
                    server_name=server,
                    library_name=library,
                    webhook_name=webhook,
                    detected_at=detected,
                    sent_at=item.sent_at,
                    next_retry_at=item.next_retry_at,
                    sending_started_at=item.sending_started_at,
                    status=item.status,
                    attempt_count=item.attempt_count,
                    last_error=item.last_error,
                    discord_message_id=item.discord_message_id,
                )
                for item, title, server, library, webhook, detected in rows
            ]

    def retry(self, queue_item_id: int, *, confirm_sent_resend: bool = False, now: datetime | None = None) -> None:
        """Request one target retry; successful prior delivery needs explicit confirmation."""

        timestamp = now or datetime.now(UTC)
        with self._session_factory() as session:
            with session.begin():
                item = session.get(NotificationQueueItem, queue_item_id)
                if item is None:
                    raise ValueError("Notification queue item does not exist")
                if item.status == QueueStatus.SENDING:
                    raise ValueError("Notification is currently being sent")
                if item.status not in {QueueStatus.FAILED, QueueStatus.RETRY, QueueStatus.SENT}:
                    raise ValueError("Only failed, retrying or sent notifications can be retried")
                if item.status == QueueStatus.SENT and not confirm_sent_resend:
                    raise ValueError("Resending a successful notification requires explicit confirmation")
                item.status = QueueStatus.READY
                # A deliberate manual retry gets a fresh attempt budget; immutable
                # history retains prior attempts and successful message IDs.
                item.attempt_count = 0
                item.next_retry_at = timestamp
                item.sending_started_at = None
                item.last_error = None
                item.sent_at = None
                item.discord_message_id = None
                item.event.status = EventStatus.READY
                session.add(
                    NotificationHistory(
                        queue_item_id=item.id,
                        status=QueueStatus.READY,
                        attempted_at=timestamp,
                        error="Manual retry requested",
                    )
                )
