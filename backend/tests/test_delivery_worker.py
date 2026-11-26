from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import Event, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.providers.notifications.discord.client import DiscordDeliveryError
from app.queue.state import mark_event_ready
from app.queue.worker import DiscordDeliveryWorker, OutgoingNotification, WebhookTarget
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory


class Resolver:
    """No-crypto resolver for worker orchestration tests."""

    def resolve(self, webhook_id: int) -> WebhookTarget:
        return WebhookTarget(webhook_id=webhook_id, webhook_url=f"https://discord.example/{webhook_id}")


class Builder:
    """Stable payload builder used to focus tests on worker transitions."""

    def build(self, _event_id: int) -> OutgoingNotification:
        return OutgoingNotification(embed={"title": "New"})


class Sender:
    """Controllable transport that records target-specific worker calls."""

    def __init__(self, error: DiscordDeliveryError | None = None) -> None:
        self.error = error
        self.sent_webhook_ids: list[int] = []

    async def send(self, target: WebhookTarget, _notification: OutgoingNotification) -> tuple[str | None, int]:
        self.sent_webhook_ids.append(target.webhook_id)
        if self.error is not None:
            raise self.error
        return f"message-{target.webhook_id}", 200


@pytest.fixture
def delivery_setup(tmp_path: Path) -> tuple[sessionmaker[Session], Event]:
    """Persist one metadata-ready event routed to two independent destinations."""

    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, bookorbit_library_id=4, name="Books", monitored=True)
        library.webhooks.extend([Webhook(name="A", url_encrypted="a"), Webhook(name="B", url_encrypted="b")])
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
    with factory.begin() as session:
        server = session.scalar(select(Server))
        library = session.scalar(select(Library))
        assert server is not None and library is not None
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
    with factory() as session:
        event = session.scalar(select(Event))
        assert event is not None
        return factory, event


@pytest.mark.asyncio
async def test_worker_sends_each_ready_destination_once(delivery_setup: tuple[sessionmaker[Session], Event]) -> None:
    """One pass claims, commits, sends, and records each routed Discord destination."""

    factory, _event = delivery_setup
    sender = Sender()
    worker = DiscordDeliveryWorker(factory, Resolver(), Builder(), sender)

    report = await worker.process_once(now=datetime(2026, 11, 26, tzinfo=UTC))

    assert report.claimed == 2
    assert report.sent == 2
    assert sorted(sender.sent_webhook_ids) == [1, 2]
    with factory() as session:
        assert {item.status for item in session.scalars(select(NotificationQueueItem)).all()} == {QueueStatus.SENT}


@pytest.mark.asyncio
async def test_worker_records_discord_rate_limit_for_retry(delivery_setup: tuple[sessionmaker[Session], Event]) -> None:
    """Transport rate limits update durable retry state instead of losing delivery work."""

    factory, _event = delivery_setup
    worker = DiscordDeliveryWorker(factory, Resolver(), Builder(), Sender(DiscordDeliveryError(429, retry_after_seconds=4)))

    report = await worker.process_once(now=datetime(2026, 11, 26, tzinfo=UTC), limit=1)

    assert report.retried == 1
    with factory() as session:
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None
        assert item.status == QueueStatus.RETRY
        assert item.last_error == "Discord delivery failed (HTTP 429)"
