"""Administrator-facing notification status and explicit retry operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import NotificationHistory, NotificationQueueItem, QueueStatus

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
                if item.status == QueueStatus.SENT and not confirm_sent_resend:
                    raise ValueError("Resending a successful notification requires explicit confirmation")
                item.status = QueueStatus.READY
                item.next_retry_at = timestamp
                item.sending_started_at = None
                item.last_error = None
                session.add(
                    NotificationHistory(
                        queue_item_id=item.id,
                        status=QueueStatus.READY,
                        attempted_at=timestamp,
                        error="Manual retry requested",
                    )
                )
