"""Delayed source-detail refresh before an event becomes eligible for delivery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models import Book, Event, EventStatus
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.queue.state import mark_event_ready
from app.schemas.bookorbit import BookOrbitBookDetail

type SessionFactory = Callable[[], Session]


class BookDetailClient(Protocol):
    """Narrow detail capability needed by the metadata wait worker."""

    async def get_book(self, book_id: int) -> BookOrbitBookDetail:
        """Return the current detail record for one accessible source book."""


@dataclass(frozen=True, slots=True)
class MetadataRefreshReport:
    """Counts suitable for system status without exposing media metadata."""

    checked: int
    released: int
    deferred: int
    failed: int


class MetadataRefreshService:
    """Re-fetch new books after source metadata import has had time to finish."""

    def __init__(self, session_factory: SessionFactory, *, retry_seconds: int = 30) -> None:
        if retry_seconds < 1:
            raise ValueError("Metadata retry interval must be positive")
        self._session_factory = session_factory
        self._retry_seconds = retry_seconds

    async def process_due_events(
        self,
        server_id: int,
        client: BookDetailClient,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> MetadataRefreshReport:
        """Refresh a bounded set of due events without holding database transactions over HTTP."""

        if limit < 1 or limit > 100:
            raise ValueError("Metadata refresh limit must be between 1 and 100")
        timestamp = now or datetime.now(UTC)
        due = self._load_due_events(server_id, timestamp, limit)
        released = deferred = failed = 0
        for event_id, source_book_id in due:
            try:
                detail = await client.get_book(source_book_id)
            except BookOrbitApiError as error:
                outcome = self._record_fetch_failure(event_id, str(error), timestamp)
                failed += 1
            else:
                outcome = self._record_detail(event_id, detail, timestamp)
            if outcome == "released":
                released += 1
            elif outcome == "deferred":
                deferred += 1
        return MetadataRefreshReport(checked=len(due), released=released, deferred=deferred, failed=failed)

    def _load_due_events(self, server_id: int, now: datetime, limit: int) -> list[tuple[int, int]]:
        """Read just IDs needed for HTTP refresh; ORM rows do not escape the session."""

        with self._session_factory() as session:
            rows = session.execute(
                select(Event.id, Book.bookorbit_book_id)
                .join(Book, Event.book_id == Book.id)
                .where(
                    Event.server_id == server_id,
                    Event.status == EventStatus.WAITING_FOR_METADATA,
                    or_(Event.metadata_not_before_at.is_(None), Event.metadata_not_before_at <= now),
                )
                .order_by(Event.metadata_not_before_at, Event.id)
                .limit(limit)
            ).all()
        return [(int(row.id), int(row.bookorbit_book_id)) for row in rows]

    def _record_detail(self, event_id: int, detail: BookOrbitBookDetail, now: datetime) -> str:
        """Store current source details and release or retry according to the deadline."""

        with self._session_factory() as session:
            with session.begin():
                event = session.get(Event, event_id)
                if event is None or event.status != EventStatus.WAITING_FOR_METADATA:
                    return "deferred"
                book = event.book
                book.title = detail.title
                book.authors_json = [author["name"] for author in detail.authors if isinstance(author.get("name"), str)]
                book.metadata_json = detail.model_dump(mode="json", by_alias=True)
                book.source_added_at = detail.added_at
                book.source_updated_at = detail.updated_at
                event.metadata_attempt_count += 1
                event.metadata_last_error = None
                if _is_publishable(detail) or _deadline_reached(event.metadata_deadline_at, now):
                    mark_event_ready(session, event.id)
                    return "released"
                event.metadata_not_before_at = _next_refresh(event.metadata_deadline_at, now, self._retry_seconds)
        return "deferred"

    def _record_fetch_failure(self, event_id: int, error: str, now: datetime) -> str:
        """Defer temporary source failures, but eventually release already known metadata."""

        with self._session_factory() as session:
            with session.begin():
                event = session.get(Event, event_id)
                if event is None or event.status != EventStatus.WAITING_FOR_METADATA:
                    return "deferred"
                event.metadata_attempt_count += 1
                event.metadata_last_error = _safe_error(error)
                if _deadline_reached(event.metadata_deadline_at, now):
                    mark_event_ready(session, event.id)
                    return "released"
                event.metadata_not_before_at = _next_refresh(event.metadata_deadline_at, now, self._retry_seconds)
        return "deferred"


def _is_publishable(detail: BookOrbitBookDetail) -> bool:
    """Only a non-empty title delays publication; optional fields never block delivery."""

    return bool(detail.title and detail.title.strip())


def _deadline_reached(deadline: datetime | None, now: datetime) -> bool:
    """SQLite may return naive datetimes, so normalize legacy rows to UTC explicitly."""

    if deadline is None:
        return True
    normalized = deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline.astimezone(UTC)
    return normalized <= now


def _next_refresh(deadline: datetime | None, now: datetime, retry_seconds: int) -> datetime:
    """Do not schedule a retry after the configured deadline; the next scan may still be later."""

    next_retry = now + timedelta(seconds=retry_seconds)
    if deadline is None:
        return next_retry
    normalized = deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline.astimezone(UTC)
    return min(next_retry, normalized)


def _safe_error(value: str) -> str:
    """Preserve only concise client error context; BookOrbit client errors contain no response body."""

    return " ".join(value.split())[:2_000] or "Metadata refresh failed"
