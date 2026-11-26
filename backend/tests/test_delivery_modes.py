"""Integration coverage for durable per-library delivery aggregation modes."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import DeliveryMode, Event, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.providers.notifications.discord.client import DiscordDeliveryError
from app.queue.state import claim_due_deliveries, mark_event_ready
from app.queue.worker import DiscordDeliveryWorker, OutgoingNotification, WebhookTarget
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.schemas.bookorbit import CoverImage


class Resolver:
    """No-crypto resolver used to isolate delivery aggregation behavior."""

    def resolve(self, webhook_id: int) -> WebhookTarget:
        return WebhookTarget(webhook_id=webhook_id, webhook_url=f"https://discord.example/{webhook_id}")


class Builder:
    """Build attachment-free embeds, which Discord can place in one grouped message."""

    def build(self, event_id: int) -> OutgoingNotification:
        return OutgoingNotification(embed={"title": f"Book {event_id}"})


class BatchSender:
    """Capture the number of actual Discord requests without making network calls."""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def send(self, _target: WebhookTarget, _notification: OutgoingNotification) -> tuple[str | None, int]:
        raise AssertionError("Batched events should use one grouped Discord request")

    async def send_many(self, _target: WebhookTarget, notifications: list[OutgoingNotification]) -> tuple[str | None, int]:
        self.batch_sizes.append(len(notifications))
        return "batch-message", 200


@pytest.fixture
def batch_setup(tmp_path: Path) -> tuple[sessionmaker[Session], datetime]:
    """Prepare two independent events that enter the same active collection window."""

    engine = create_engine(f"sqlite:///{tmp_path / 'delivery-modes.db'}")
    factory = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(
            server=server,
            bookorbit_library_id=1,
            name="Books",
            monitored=True,
            delivery_mode=DeliveryMode.BATCH,
            batch_window_seconds=60,
        )
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
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing"), ObservedBook(bookorbit_book_id=2, title="First")],
            scan_complete=True,
        )
        first_event = session.scalar(select(Event))
        assert first_event is not None
        mark_event_ready(session, first_event.id, now=started_at)
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[
                ObservedBook(bookorbit_book_id=1, title="Existing"),
                ObservedBook(bookorbit_book_id=2, title="First"),
                ObservedBook(bookorbit_book_id=3, title="Second"),
            ],
            scan_complete=True,
        )
        second_event = session.scalars(select(Event).order_by(Event.id.desc())).first()
        assert second_event is not None
        mark_event_ready(session, second_event.id, now=started_at + timedelta(seconds=10))
    yield factory, started_at
    engine.dispose()


@pytest.mark.asyncio
async def test_batch_mode_reuses_collection_deadline_and_sends_one_grouped_message(
    batch_setup: tuple[sessionmaker[Session], datetime],
) -> None:
    """Later events share the first deadline and Discord receives one two-embed message."""

    factory, started_at = batch_setup
    with factory() as session:
        items = session.scalars(select(NotificationQueueItem).order_by(NotificationQueueItem.id)).all()
        assert [item.status for item in items] == [QueueStatus.QUEUED, QueueStatus.QUEUED]
        assert {item.next_retry_at.replace(tzinfo=UTC) for item in items if item.next_retry_at} == {started_at + timedelta(seconds=60)}
    with factory.begin() as session:
        assert claim_due_deliveries(session, limit=10, now=started_at + timedelta(seconds=59)) == []

    sender = BatchSender()
    report = await DiscordDeliveryWorker(factory, Resolver(), Builder(), sender).process_once(now=started_at + timedelta(seconds=60))

    assert report.claimed == 2
    assert report.sent == 2
    assert sender.batch_sizes == [2]
    with factory() as session:
        items = session.scalars(select(NotificationQueueItem).order_by(NotificationQueueItem.id)).all()
        assert {item.status for item in items} == {QueueStatus.SENT}
        assert {item.discord_message_id for item in items} == {"batch-message"}


@pytest.mark.asyncio
async def test_batch_splits_when_discord_combined_embed_limit_would_be_exceeded(
    batch_setup: tuple[sessionmaker[Session], datetime],
) -> None:
    """Two individually valid long embeds must be sent in separate Discord messages."""

    factory, started_at = batch_setup

    class LargeBuilder:
        def build(self, _event_id: int) -> OutgoingNotification:
            return OutgoingNotification(embed={"title": "Book", "description": "x" * 3500})

    sender = BatchSender()
    report = await DiscordDeliveryWorker(factory, Resolver(), LargeBuilder(), sender).process_once(now=started_at + timedelta(seconds=60))
    assert report.sent == 2 and sender.batch_sizes == [1, 1]
    with factory() as session:
        assert {item.status for item in session.scalars(select(NotificationQueueItem)).all()} == {QueueStatus.SENT}


@pytest.mark.asyncio
async def test_split_batch_failure_does_not_undo_successful_subgroup(batch_setup: tuple[sessionmaker[Session], datetime]) -> None:
    factory, started_at = batch_setup

    class LargeBuilder:
        def build(self, _event_id: int) -> OutgoingNotification:
            return OutgoingNotification(embed={"description": "x" * 3500})

    class PartialSender(BatchSender):
        async def send_many(self, target: WebhookTarget, notifications: list[OutgoingNotification]) -> tuple[str | None, int]:
            if self.batch_sizes:
                raise DiscordDeliveryError(429, retry_after_seconds=30)
            return await super().send_many(target, notifications)

    report = await DiscordDeliveryWorker(factory, Resolver(), LargeBuilder(), PartialSender()).process_once(
        now=started_at + timedelta(seconds=60)
    )
    assert report.sent == 1 and report.retried == 1
    with factory() as session:
        assert {item.status for item in session.scalars(select(NotificationQueueItem)).all()} == {QueueStatus.SENT, QueueStatus.RETRY}


@pytest.mark.asyncio
async def test_group_with_covers_sends_individually_without_refetching(batch_setup: tuple[sessionmaker[Session], datetime]) -> None:
    """Each attachment remains with its book and a failed send leaves only that row retryable."""

    factory, started_at = batch_setup

    class CoverBuilder:
        def build(self, event_id: int) -> OutgoingNotification:
            return OutgoingNotification(embed={"title": str(event_id)}, cover_source=(1, event_id))

    class Covers:
        def __init__(self) -> None:
            self.requests: list[tuple[int, int]] = []

        async def get_cover(self, server_id: int, book_id: int) -> CoverImage:
            self.requests.append((server_id, book_id))
            return CoverImage(content=str(book_id).encode(), content_type="image/png", filename=f"{book_id}.png")

    class IndividualSender(BatchSender):
        def __init__(self) -> None:
            super().__init__()
            self.covers: list[bytes] = []

        async def send(self, _target: WebhookTarget, notification: OutgoingNotification) -> tuple[str | None, int]:
            assert notification.cover is not None
            self.covers.append(notification.cover.content)
            if len(self.covers) == 2:
                raise DiscordDeliveryError(429)
            return "first-message", 200

    covers, sender = Covers(), IndividualSender()
    report = await DiscordDeliveryWorker(factory, Resolver(), CoverBuilder(), sender, cover_provider=covers).process_once(
        now=started_at + timedelta(seconds=60)
    )
    assert report.sent == 1 and report.retried == 1
    assert len(covers.requests) == len(sender.covers) == 2
    assert sender.batch_sizes == []
    with factory() as session:
        assert {item.status for item in session.scalars(select(NotificationQueueItem)).all()} == {QueueStatus.SENT, QueueStatus.RETRY}


def test_daily_summary_uses_the_next_configured_local_time(tmp_path: Path) -> None:
    """Daily summaries are deferred in UTC while respecting the library's IANA timezone."""

    engine = create_engine(f"sqlite:///{tmp_path / 'daily-summary.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        library = Library(
            server=Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted"),
            bookorbit_library_id=1,
            name="Books",
            monitored=True,
            delivery_mode=DeliveryMode.DAILY_SUMMARY,
            daily_summary_time="18:00",
            timezone="Europe/Berlin",
        )
        library.webhooks.append(Webhook(name="Target", url_encrypted="encrypted"))
        session.add(library)
        session.commit()
        reconcile_library_inventory(
            session,
            server_id=library.server_id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing")],
            scan_complete=True,
        )
        reconcile_library_inventory(
            session,
            server_id=library.server_id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing"), ObservedBook(bookorbit_book_id=2, title="New")],
            scan_complete=True,
        )
        event = session.scalar(select(Event))
        assert event is not None
        mark_event_ready(session, event.id, now=datetime(2026, 1, 1, 16, 0, tzinfo=UTC))
        session.commit()
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None
        assert item.status == QueueStatus.QUEUED
        assert item.next_retry_at == datetime(2026, 1, 1, 17, 0)
    finally:
        session.close()
        engine.dispose()
