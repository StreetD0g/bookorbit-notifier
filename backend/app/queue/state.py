"""Transactional delivery state machine independent from Discord HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.database.models import DeliveryMode, Event, EventStatus, Library, NotificationHistory, NotificationQueueItem, QueueStatus

TERMINAL_QUEUE_STATUSES = {QueueStatus.SENT, QueueStatus.FAILED, QueueStatus.SKIPPED}


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    """Minimal non-secret data a delivery worker needs after claiming an outbox row."""

    queue_item_id: int
    event_id: int
    webhook_id: int
    library_id: int
    delivery_mode: DeliveryMode
    attempt_count: int


def mark_event_ready(session: Session, event_id: int, *, now: datetime | None = None) -> int:
    """Release an event's per-webhook rows after metadata is ready to publish."""

    event = session.get(Event, event_id)
    if event is None:
        raise ValueError("Event does not exist")
    if event.status in {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.SKIPPED}:
        return 0

    timestamp = now or datetime.now(UTC)
    library = event.book.library
    scheduled_status, scheduled_at = _delivery_schedule(library.delivery_mode, library, timestamp)
    if library.delivery_mode == DeliveryMode.BATCH:
        # The first ready event opens a collection window. Later events for the
        # same library share that deadline, rather than each creating a nearly
        # identical Discord message a few seconds later.
        existing_deadline = session.scalar(
            select(func.min(NotificationQueueItem.next_retry_at))
            .join(Event, NotificationQueueItem.event_id == Event.id)
            .where(
                Event.library_id == library.id,
                Event.id != event.id,
                NotificationQueueItem.status == QueueStatus.QUEUED,
                NotificationQueueItem.next_retry_at.is_not(None),
            )
        )
        if existing_deadline is not None:
            scheduled_at = existing_deadline
    items = session.scalars(select(NotificationQueueItem).where(NotificationQueueItem.event_id == event_id)).all()
    promoted = 0
    for item in items:
        if item.status == QueueStatus.WAITING_FOR_METADATA:
            item.status = scheduled_status
            item.next_retry_at = scheduled_at
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
        and_(NotificationQueueItem.status == QueueStatus.QUEUED, NotificationQueueItem.next_retry_at <= timestamp),
        and_(
            NotificationQueueItem.status == QueueStatus.RETRY,
            or_(NotificationQueueItem.next_retry_at.is_(None), NotificationQueueItem.next_retry_at <= timestamp),
        ),
    )
    rows = session.execute(
        select(NotificationQueueItem, Event.library_id, Library.delivery_mode)
        .join(Event, NotificationQueueItem.event_id == Event.id)
        .join(Library, Event.library_id == Library.id)
        .where(due)
        .order_by(NotificationQueueItem.next_retry_at, NotificationQueueItem.created_at, NotificationQueueItem.id)
        .limit(limit)
    ).all()
    claims: list[DeliveryClaim] = []
    for item, library_id, delivery_mode in rows:
        item.status = QueueStatus.SENDING
        item.attempt_count += 1
        item.sending_started_at = timestamp
        claims.append(
            DeliveryClaim(
                queue_item_id=item.id,
                event_id=item.event_id,
                webhook_id=item.webhook_id,
                library_id=library_id,
                delivery_mode=delivery_mode,
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
    item.sending_started_at = None
    session.add(
        NotificationHistory(
            queue_item_id=item.id,
            status=QueueStatus.SENT,
            attempted_at=item.sent_at,
            discord_message_id=discord_message_id,
        )
    )
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
    item.sending_started_at = None
    if item.attempt_count >= max_attempts:
        item.status = QueueStatus.FAILED
        item.next_retry_at = None
    else:
        item.status = QueueStatus.RETRY
        item.next_retry_at = timestamp + timedelta(seconds=_retry_delay_seconds(item.attempt_count, retry_after_seconds))
    session.add(
        NotificationHistory(
            queue_item_id=item.id,
            status=item.status,
            attempted_at=timestamp,
            error=item.last_error,
        )
    )
    _refresh_event_completion(session, item.event_id)


def _require_sending_item(session: Session, queue_item_id: int) -> NotificationQueueItem:
    """Reject stale/double worker completion calls instead of silently corrupting status."""

    item = session.get(NotificationQueueItem, queue_item_id)
    if item is None:
        raise ValueError("Notification queue item does not exist")
    if item.status != QueueStatus.SENDING:
        raise ValueError("Notification queue item is not currently being sent")
    return item


def recover_stale_sends(session: Session, *, stale_after: timedelta, now: datetime | None = None) -> int:
    """Return interrupted worker claims to retry after a container crash or restart.

    The original Discord request may have reached the destination before the process
    died, so this cannot guarantee exactly-once delivery. It preserves the event and
    limits recovery to the affected webhook rather than duplicating sibling sends.
    """

    if stale_after.total_seconds() <= 0:
        raise ValueError("Stale-send interval must be positive")
    timestamp = now or datetime.now(UTC)
    stale_before = timestamp - stale_after
    items = session.scalars(
        select(NotificationQueueItem).where(
            NotificationQueueItem.status == QueueStatus.SENDING,
            or_(
                NotificationQueueItem.sending_started_at.is_(None),
                NotificationQueueItem.sending_started_at <= stale_before,
            ),
        )
    ).all()
    for item in items:
        item.status = QueueStatus.RETRY
        item.sending_started_at = None
        item.next_retry_at = timestamp
        item.last_error = "Delivery interrupted before a result was persisted"
        session.add(
            NotificationHistory(
                queue_item_id=item.id,
                status=QueueStatus.RETRY,
                attempted_at=timestamp,
                error=item.last_error,
            )
        )
    return len(items)


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


def _delivery_schedule(delivery_mode: DeliveryMode, library: Library, now: datetime) -> tuple[QueueStatus, datetime | None]:
    """Choose the durable queue state and due timestamp for one library's configured mode."""

    if delivery_mode == DeliveryMode.SINGLE:
        return QueueStatus.READY, None
    if delivery_mode == DeliveryMode.BATCH:
        window = max(1, library.batch_window_seconds)
        return QueueStatus.QUEUED, now + timedelta(seconds=window)
    return QueueStatus.QUEUED, _next_daily_summary(library.daily_summary_time, library.timezone, now)


def _next_daily_summary(summary_time: str, timezone_name: str, now: datetime) -> datetime:
    """Return the next configured local summary time as a UTC timestamp, including DST zones."""

    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Library timezone is not available") from error
    try:
        hour, minute = (int(part) for part in summary_time.split(":", maxsplit=1))
        local_time = time(hour=hour, minute=minute)
    except (TypeError, ValueError) as error:
        raise ValueError("Daily summary time must use HH:MM") from error
    local_now = now.astimezone(zone)
    local_target = datetime.combine(local_now.date(), local_time, tzinfo=zone)
    if local_target <= local_now:
        local_target += timedelta(days=1)
    return local_target.astimezone(UTC)
