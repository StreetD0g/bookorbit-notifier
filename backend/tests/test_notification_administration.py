from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import Event, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.queue.state import claim_due_deliveries, mark_event_ready, record_delivery_success
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.services.notifications import NotificationAdministrationService


@pytest.fixture
def sent_notification(tmp_path: Path) -> tuple[sessionmaker[Session], NotificationQueueItem]:
    """Create a completed destination delivery with a durable history record."""

    engine = create_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, bookorbit_library_id=1, name="Books", monitored=True)
        library.webhooks.append(Webhook(name="Target", url_encrypted="encrypted"))
        session.add_all([server, library])
    with factory.begin() as session:
        server = session.scalar(select(Server))
        library = session.scalar(select(Library))
        assert server is not None and library is not None
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing")],
            scan_complete=True,
        )
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing"), ObservedBook(bookorbit_book_id=2, title="New")],
            scan_complete=True,
        )
        event = session.scalar(select(Event))
        assert event is not None
        mark_event_ready(session, event.id)
        claim = claim_due_deliveries(session, limit=1, now=datetime(2026, 11, 26, tzinfo=UTC))[0]
        record_delivery_success(session, queue_item_id=claim.queue_item_id, discord_message_id="message-1")
    with factory() as session:
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None
        return factory, item


def test_manual_resend_of_sent_message_requires_confirmation(
    sent_notification: tuple[sessionmaker[Session], NotificationQueueItem],
) -> None:
    """A human must explicitly acknowledge that a second Discord message will be created."""

    factory, item = sent_notification
    administration = NotificationAdministrationService(factory)

    with pytest.raises(ValueError, match="explicit confirmation"):
        administration.retry(item.id)
    administration.retry(item.id, confirm_sent_resend=True, now=datetime(2026, 11, 26, tzinfo=UTC))

    with factory() as session:
        persisted = session.get(NotificationQueueItem, item.id)
        assert persisted is not None and persisted.status == QueueStatus.READY
    history = administration.history(item.id)
    assert [entry.status for entry in history] == [QueueStatus.SENT, QueueStatus.READY]
    assert history[0].discord_message_id == "message-1"


def test_summary_counts_persistent_delivery_state(sent_notification: tuple[sessionmaker[Session], NotificationQueueItem]) -> None:
    """Dashboard status derives from the database instead of transient worker memory."""

    factory, _item = sent_notification
    summary = NotificationAdministrationService(factory).summary()

    assert summary.sent == 1
    assert summary.failed == 0
    assert summary.retry == 0
