"""Inventory reconciliation that keeps baseline, event detection, and outbox rows atomic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Book,
    Event,
    EventStatus,
    EventType,
    Library,
    NotificationQueueItem,
    QueueStatus,
    ScanHistory,
    ScanStatus,
    Webhook,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class ObservedBook:
    """Minimal source information needed to preserve identity and refresh a record."""

    bookorbit_book_id: int
    title: str | None
    authors: list[str] = field(default_factory=list)
    source_added_at: str | None = None
    source_updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Outcome usable by a scheduler without exposing source credentials."""

    baseline_created: bool
    scan_status: ScanStatus
    books_seen: int
    books_added: int
    events_created: int
    deliveries_queued: int


def reconcile_library_inventory(
    session: Session,
    *,
    server_id: int,
    library_id: int,
    observed_books: Sequence[ObservedBook],
    scan_complete: bool,
    allow_initial_notifications: bool = False,
    started_at: datetime | None = None,
    incomplete_reason: str | None = None,
) -> ReconciliationResult:
    """Persist one scan in a transaction and enqueue deliveries only for true new IDs.

    A first *complete* scan becomes a silent baseline unless the caller already
    collected explicit administrator confirmation. A first partial scan stays
    unbaselined, preventing its unseen old books from being mistaken for arrivals
    when the next complete scan succeeds.
    """

    library = session.scalar(select(Library).where(Library.id == library_id, Library.server_id == server_id))
    if library is None:
        raise ValueError("Library does not belong to the supplied server")

    unique_observed = _deduplicate_observations(observed_books)
    now = utc_now()
    had_baseline = library.baseline_completed_at is not None
    existing = _existing_books(session, server_id, unique_observed)
    new_books: list[Book] = []

    for observed in unique_observed:
        book = existing.get(observed.bookorbit_book_id)
        if book is None:
            book = Book(
                server_id=server_id,
                library_id=library.id,
                bookorbit_book_id=observed.bookorbit_book_id,
                title=observed.title,
                authors_json=observed.authors,
                metadata_json=observed.metadata,
                first_seen_at=now,
                last_seen_at=now,
                source_added_at=observed.source_added_at,
                source_updated_at=observed.source_updated_at,
            )
            session.add(book)
            existing[book.bookorbit_book_id] = book
            new_books.append(book)
        else:
            # A source move remains one logical BookOrbit ID on the same server.
            book.library_id = library.id
            book.title = observed.title
            book.authors_json = observed.authors
            book.metadata_json = observed.metadata
            book.last_seen_at = now
            book.source_added_at = observed.source_added_at
            book.source_updated_at = observed.source_updated_at

    session.flush()  # New book IDs are required as durable Event foreign keys.

    should_publish = had_baseline or allow_initial_notifications
    events_created, deliveries_queued = _create_arrival_events(session, library, new_books, should_publish)
    if scan_complete and not had_baseline:
        library.baseline_completed_at = now

    scan_status = ScanStatus.SUCCEEDED if scan_complete else ScanStatus.PARTIAL
    session.add(
        ScanHistory(
            server_id=server_id,
            library_id=library.id,
            status=scan_status,
            started_at=started_at or now,
            completed_at=now,
            books_seen=len(unique_observed),
            books_added=len(new_books),
            error_message=None if scan_complete else incomplete_reason or "Source inventory was incomplete",
        )
    )
    session.flush()
    return ReconciliationResult(
        baseline_created=scan_complete and not had_baseline,
        scan_status=scan_status,
        books_seen=len(unique_observed),
        books_added=len(new_books),
        events_created=events_created,
        deliveries_queued=deliveries_queued,
    )


def record_failed_scan(
    session: Session,
    *,
    server_id: int,
    library_id: int,
    error_message: str,
    started_at: datetime | None = None,
) -> None:
    """Record a source failure without changing inventory or removal state."""

    library = session.scalar(select(Library).where(Library.id == library_id, Library.server_id == server_id))
    if library is None:
        raise ValueError("Library does not belong to the supplied server")
    now = utc_now()
    session.add(
        ScanHistory(
            server_id=server_id,
            library_id=library_id,
            status=ScanStatus.FAILED,
            started_at=started_at or now,
            completed_at=now,
            books_seen=0,
            books_added=0,
            error_message=error_message[:2000],
        )
    )


def _deduplicate_observations(observed_books: Sequence[ObservedBook]) -> list[ObservedBook]:
    """Fail closed if unstable pagination reports the same source ID twice in one scan."""

    unique: dict[int, ObservedBook] = {}
    for observed in observed_books:
        if observed.bookorbit_book_id <= 0:
            raise ValueError("BookOrbit book IDs must be positive integers")
        if observed.bookorbit_book_id in unique:
            raise ValueError("Source inventory contains a duplicate BookOrbit book ID")
        unique[observed.bookorbit_book_id] = observed
    return list(unique.values())


def _existing_books(session: Session, server_id: int, observed_books: Sequence[ObservedBook]) -> dict[int, Book]:
    """Fetch existing identities in one bounded query."""

    ids = [book.bookorbit_book_id for book in observed_books]
    if not ids:
        return {}
    books = session.scalars(select(Book).where(Book.server_id == server_id, Book.bookorbit_book_id.in_(ids))).all()
    return {book.bookorbit_book_id: book for book in books}


def _create_arrival_events(session: Session, library: Library, new_books: Sequence[Book], should_publish: bool) -> tuple[int, int]:
    """Create durable events and one waiting delivery row per enabled route."""

    if not should_publish or not new_books:
        return 0, 0
    webhooks = session.scalars(
        select(Webhook).join(Webhook.libraries).where(Library.id == library.id, Webhook.enabled.is_(True))
    ).all()
    delivery_count = 0
    for book in new_books:
        event = Event(
            server_id=book.server_id,
            library_id=library.id,
            book_id=book.id,
            event_type=EventType.BOOK_ADDED,
            event_data={"provider": "bookorbit_polling", "bookorbit_book_id": book.bookorbit_book_id},
            status=EventStatus.WAITING_FOR_METADATA,
            metadata_not_before_at=utc_now() + timedelta(seconds=library.metadata_delay_seconds),
            metadata_deadline_at=utc_now() + timedelta(seconds=library.metadata_max_wait_seconds),
        )
        session.add(event)
        session.flush()
        for webhook in webhooks:
            session.add(
                NotificationQueueItem(
                    event_id=event.id,
                    webhook_id=webhook.id,
                    status=QueueStatus.WAITING_FOR_METADATA,
                )
            )
            delivery_count += 1
    return len(new_books), delivery_count
