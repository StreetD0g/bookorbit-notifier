from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import Event, EventStatus, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.queue.state import claim_due_deliveries, mark_event_ready, record_delivery_failure, record_delivery_success
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory


@pytest.fixture
def queued_event(tmp_path: Path) -> tuple[Session, Event, list[NotificationQueueItem]]:
    """Create a mature library with two routed Discord destinations."""

    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
    library = Library(server=server, bookorbit_library_id=5, name="Books", monitored=True)
    library.webhooks.extend(
        [Webhook(name="Target A", url_encrypted="encrypted-a"), Webhook(name="Target B", url_encrypted="encrypted-b")]
    )
    session.add_all([server, library])
    session.commit()
    reconcile_library_inventory(
        session,
        server_id=server.id,
        library_id=library.id,
        observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing")],
        scan_complete=True,
    )
    session.commit()
    reconcile_library_inventory(
        session,
        server_id=server.id,
        library_id=library.id,
        observed_books=[
            ObservedBook(bookorbit_book_id=1, title="Existing"),
            ObservedBook(bookorbit_book_id=2, title="New"),
        ],
        scan_complete=True,
    )
    session.commit()
    event = session.scalar(select(Event))
    assert event is not None
    items = session.scalars(select(NotificationQueueItem).order_by(NotificationQueueItem.id)).all()
    yield session, event, items
    session.close()
    engine.dispose()


def test_destination_failure_does_not_repeat_successful_sibling(
    queued_event: tuple[Session, Event, list[NotificationQueueItem]],
) -> None:
    """A successful channel remains sent while only the failed target becomes retryable."""

    session, event, _items = queued_event
    assert mark_event_ready(session, event.id) == 2
    session.commit()
    claims = claim_due_deliveries(session, limit=10, now=datetime(2026, 11, 26, tzinfo=UTC))
    session.commit()

    record_delivery_success(session, queue_item_id=claims[0].queue_item_id, discord_message_id="message-1")
    record_delivery_failure(
        session,
        queue_item_id=claims[1].queue_item_id,
        error_summary="Discord HTTP 429",
        retry_after_seconds=2.5,
        now=datetime(2026, 11, 26, tzinfo=UTC),
    )
    session.commit()

    items = session.scalars(select(NotificationQueueItem).order_by(NotificationQueueItem.id)).all()
    assert [item.status for item in items] == [QueueStatus.SENT, QueueStatus.RETRY]
    assert items[0].discord_message_id == "message-1"
    assert items[1].next_retry_at == datetime(2026, 11, 26, 0, 0, 2, 500_000)
    session.refresh(event)
    assert event.status == EventStatus.READY


def test_event_completes_after_retry_succeeds(queued_event: tuple[Session, Event, list[NotificationQueueItem]]) -> None:
    """A retry consumes only its own outbox row and completes the shared event last."""

    session, event, _items = queued_event
    mark_event_ready(session, event.id)
    claims = claim_due_deliveries(session, limit=10, now=datetime(2026, 11, 26, tzinfo=UTC))
    record_delivery_success(session, queue_item_id=claims[0].queue_item_id, discord_message_id="message-1")
    record_delivery_failure(
        session,
        queue_item_id=claims[1].queue_item_id,
        error_summary="temporary failure",
        retry_after_seconds=1,
        now=datetime(2026, 11, 26, tzinfo=UTC),
    )
    session.commit()

    retry_claim = claim_due_deliveries(session, limit=10, now=datetime(2026, 11, 26, tzinfo=UTC) + timedelta(seconds=1))
    assert [claim.queue_item_id for claim in retry_claim] == [claims[1].queue_item_id]
    record_delivery_success(session, queue_item_id=retry_claim[0].queue_item_id, discord_message_id="message-2")
    session.commit()

    session.refresh(event)
    assert event.status == EventStatus.COMPLETED


def test_delivery_claim_validates_safe_batch_limit(queued_event: tuple[Session, Event, list[NotificationQueueItem]]) -> None:
    """Workers cannot accidentally lock an unbounded amount of persistent work."""

    session, _event, _items = queued_event
    with pytest.raises(ValueError, match="between 1 and 100"):
        claim_due_deliveries(session, limit=0)
