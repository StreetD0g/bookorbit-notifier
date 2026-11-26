"""Transactional delivery state machine independent from Discord HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.database.models import Event, EventStatus, NotificationQueueItem, QueueStatus

TERMINAL_QUEUE_STATUSES = {QueueStatus.SENT, QueueStatus.FAILED, QueueStatus.SKIPPED}


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    """Minimal non-secret data a delivery worker needs after claiming an outbox row."""

    queue_item_id: int
    event_id: int
    webhook_id: int
    attempt_count: int


def mark_event_ready(session: Session, event_id: int) -> int:
    """Release an event's per-webhook rows after metadata is ready to publish."""

    event = session.get(Event, event_id)
    if event is None:
        raise ValueError("Event does not exist")
    if event.status in {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.SKIPPED}:
        return 0

    items = session.scalars(select(NotificationQueueItem).where(NotificationQueueItem.event_id == event_id)).all()
    promoted = 0
    for item in items:
        if item.status == QueueStatus.WAITING_FOR_METADATA:
            item.status = QueueStatus.READY
            promoted += 1
    event.status = EventStatus.READY
    return promoted


def claim_due_deliveries(session: Session, *, limit: int, now: datetime | None = None) -> list[DeliveryClaim]:
    """Claim a bounded batch so only the selected rows enter `SENDING` state.

    Callers must commit immediately after this function before doing network I/O.
    That makes a restart observable: a future recovery task can move stale
    `SENDING` rows to retry rather than creating a second source event.
    """

    if limit < 1 or limit > 100:
        raise ValueError("Delivery claim limit must be between 1 and 100")
    timestamp = now or datetime.now(UTC)
    due = or_(
        NotificationQueueItem.status == QueueStatus.READY,
        and_(
            NotificationQueueItem.status == QueueStatus.RETRY,
            or_(NotificationQueueItem.next_retry_at.is_(None), NotificationQueueItem.next_retry_at <= timestamp),
        ),
    )
    items = session.scalars(
        select(NotificationQueueItem).where(due).order_by(NotificationQueueItem.created_at, NotificationQueueItem.id).limit(limit)
    ).all()
    claims: list[DeliveryClaim] = []
    for item in items:
        item.status = QueueStatus.SENDING
        item.attempt_count += 1
        claims.append(
            DeliveryClaim(
                queue_item_id=item.id,
                event_id=item.event_id,
                webhook_id=item.webhook_id,
                attempt_count=item.attempt_count,
            )
        )
    return claims


def record_delivery_success(
    session: Session,
    *,
    queue_item_id: int,
    discord_message_id: str | None,
    sent_at: datetime | None = None,
) -> None:
    """Persist one destination success without changing any sibling delivery rows."""

    item = _require_sending_item(session, queue_item_id)
    item.status = QueueStatus.SENT
    item.sent_at = sent_at or datetime.now(UTC)
    item.discord_message_id = discord_message_id
    item.next_retry_at = None
    item.last_error = None
    _refresh_event_completion(session, item.event_id)


def record_delivery_failure(
    session: Session,
    *,
    queue_item_id: int,
    error_summary: str,
    retry_after_seconds: float | None = None,
    max_attempts: int = 8,
    now: datetime | None = None,
) -> None:
    """Store safe failure metadata and schedule only this webhook's next attempt."""

    if max_attempts < 1:
        raise ValueError("Maximum attempts must be positive")
    item = _require_sending_item(session, queue_item_id)
    timestamp = now or datetime.now(UTC)
    item.last_error = _safe_error_summary(error_summary)
    if item.attempt_count >= max_attempts:
        item.status = QueueStatus.FAILED
        item.next_retry_at = None
    else:
        item.status = QueueStatus.RETRY
        item.next_retry_at = timestamp + timedelta(seconds=_retry_delay_seconds(item.attempt_count, retry_after_seconds))
    _refresh_event_completion(session, item.event_id)


def _require_sending_item(session: Session, queue_item_id: int) -> NotificationQueueItem:
    """Reject stale/double worker completion calls instead of silently corrupting status."""

    item = session.get(NotificationQueueItem, queue_item_id)
    if item is None:
        raise ValueError("Notification queue item does not exist")
    if item.status != QueueStatus.SENDING:
        raise ValueError("Notification queue item is not currently being sent")
    return item


def _retry_delay_seconds(attempt_count: int, retry_after_seconds: float | None) -> float:
    """Respect a positive Discord 429 hint; otherwise use capped exponential backoff."""

    if retry_after_seconds is not None and retry_after_seconds > 0:
        return min(retry_after_seconds, 86_400)
    return min(10 * (2 ** max(attempt_count - 1, 0)), 21_600)


def _safe_error_summary(value: str) -> str:
    """Bound stored diagnostics; delivery callers must pass redacted, non-secret text."""

    summary = " ".join(value.split())
    return (summary or "Unknown delivery error")[:2_000]


def _refresh_event_completion(session: Session, event_id: int) -> None:
    """Complete an event only after every target reached a terminal state."""

    event = session.get(Event, event_id)
    if event is None:
        raise ValueError("Event does not exist")
    statuses = session.scalars(select(NotificationQueueItem.status).where(NotificationQueueItem.event_id == event_id)).all()
    if not statuses or not all(status in TERMINAL_QUEUE_STATUSES for status in statuses):
        return
    event.status = EventStatus.FAILED if QueueStatus.FAILED in statuses else EventStatus.COMPLETED
