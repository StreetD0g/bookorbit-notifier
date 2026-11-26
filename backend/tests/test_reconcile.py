from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import Event, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory


@pytest.fixture
def session(tmp_path: Path) -> Session:
    """Use a file-backed SQLite database so relational constraints are exercised."""

    engine = create_engine(f"sqlite:///{tmp_path / 'notifier.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def _create_source(session: Session) -> tuple[Server, Library]:
    server = Server(name="Test server", base_url="https://books.example", api_key_encrypted="encrypted")
    library = Library(server=server, bookorbit_library_id=42, name="Books", monitored=True)
    session.add_all([server, library])
    session.commit()
    return server, library


def _book(book_id: int, title: str = "Example") -> ObservedBook:
    return ObservedBook(bookorbit_book_id=book_id, title=title, authors=["Author"], metadata={"hasCover": True})


def test_initial_complete_scan_creates_silent_baseline(session: Session) -> None:
    """Existing books must not become notifications when monitoring first starts."""

    server, library = _create_source(session)
    result = reconcile_library_inventory(
        session, server_id=server.id, library_id=library.id, observed_books=[_book(1), _book(2)], scan_complete=True
    )
    session.commit()

    assert result.baseline_created is True
    assert result.books_added == 2
    assert result.events_created == 0
    assert session.scalar(select(func.count(Event.id))) == 0


def test_new_book_creates_one_event_and_per_webhook_delivery(session: Session) -> None:
    """A new logical ID is detected once while each target retains independent work."""

    server, library = _create_source(session)
    webhook_a = Webhook(name="Books", url_encrypted="encrypted-a")
    webhook_b = Webhook(name="Archive", url_encrypted="encrypted-b")
    library.webhooks.extend([webhook_a, webhook_b])
    session.commit()
    reconcile_library_inventory(session, server_id=server.id, library_id=library.id, observed_books=[_book(1)], scan_complete=True)
    session.commit()

    result = reconcile_library_inventory(
        session, server_id=server.id, library_id=library.id, observed_books=[_book(1), _book(2, "New")], scan_complete=True
    )
    session.commit()

    assert result.events_created == 1
    assert result.deliveries_queued == 2
    event = session.scalar(select(Event))
    assert event is not None
    deliveries = session.scalars(select(NotificationQueueItem).order_by(NotificationQueueItem.webhook_id)).all()
    assert [delivery.status for delivery in deliveries] == [QueueStatus.WAITING_FOR_METADATA, QueueStatus.WAITING_FOR_METADATA]


def test_seen_book_is_not_reported_twice(session: Session) -> None:
    """Reconciliation relies on source IDs rather than title or metadata equality."""

    server, library = _create_source(session)
    reconcile_library_inventory(session, server_id=server.id, library_id=library.id, observed_books=[_book(7)], scan_complete=True)
    session.commit()
    reconcile_library_inventory(
        session, server_id=server.id, library_id=library.id, observed_books=[_book(7, "Renamed")], scan_complete=True
    )
    session.commit()

    assert session.scalar(select(func.count(Event.id))) == 0


def test_partial_initial_scan_does_not_create_an_unsafe_baseline(session: Session) -> None:
    """A later complete scan still silences older books absent from a partial result."""

    server, library = _create_source(session)
    partial = reconcile_library_inventory(
        session,
        server_id=server.id,
        library_id=library.id,
        observed_books=[_book(1)],
        scan_complete=False,
        incomplete_reason="Second page timed out",
    )
    session.commit()
    session.refresh(library)

    complete = reconcile_library_inventory(
        session, server_id=server.id, library_id=library.id, observed_books=[_book(1), _book(2)], scan_complete=True
    )
    session.commit()

    assert partial.events_created == 0
    assert library.baseline_completed_at is not None
    assert complete.events_created == 0
    assert session.scalar(select(func.count(Event.id))) == 0
