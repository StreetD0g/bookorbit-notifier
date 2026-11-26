"""Phase-2 integration tests with simulated BookOrbit and Discord HTTP APIs."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import Event, EventStatus, Library, NotificationQueueItem, QueueStatus, ScanHistory, ScanStatus, Server, Webhook
from app.providers.events.bookorbit.client import BookOrbitClient
from app.providers.notifications.discord.client import DiscordWebhookClient
from app.queue.state import mark_event_ready
from app.queue.worker import DefaultEmbedBuilder, DiscordDeliveryWorker, OutgoingNotification, WebhookTarget
from app.scanner.polling import BookOrbitPollingService
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.services.metadata import MetadataRefreshService


class StaticWebhookResolver:
    """Keeps the HTTP integration test secret-free while exercising the worker path."""

    def resolve(self, webhook_id: int) -> WebhookTarget:
        return WebhookTarget(webhook_id=webhook_id, webhook_url="https://discord.example/api/webhooks/test")


class SimulatedDiscordSender:
    """Use the real Discord webhook client against an HTTPX in-memory transport."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def send(self, target: WebhookTarget, notification: OutgoingNotification) -> tuple[str | None, int]:
        client = DiscordWebhookClient(target.webhook_url, transport=self._transport)
        try:
            return await client.send_embed(notification.embed, cover=notification.cover)
        finally:
            await client.aclose()


@pytest.fixture
def integration_setup(tmp_path: Path) -> tuple[sessionmaker[Session], Server, Library]:
    """Persist a configured, monitored source with one Discord routing target."""

    engine = create_engine(f"sqlite:///{tmp_path / 'integration.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="unused", scan_interval_seconds=60)
        library = Library(
            server=server,
            bookorbit_library_id=17,
            name="Books",
            monitored=True,
            metadata_delay_seconds=0,
            metadata_max_wait_seconds=60,
        )
        library.webhooks.append(Webhook(name="New books", url_encrypted="unused"))
        session.add_all([server, library])
    return factory, server, library


def _book_card(book_id: int, title: str) -> dict[str, object]:
    return {"id": book_id, "libraryId": 17, "title": title, "authors": ["Author"], "files": [], "addedAt": "2026-11-26T00:00:00Z"}


def _book_detail(book_id: int, title: str) -> dict[str, object]:
    return {
        "id": book_id,
        "libraryId": 17,
        "libraryName": "Books",
        "title": title,
        "authors": [{"id": 1, "name": "Author", "sortName": None}],
        "genres": [],
        "tags": [],
        "addedAt": "2026-11-26T00:00:00Z",
        "updatedAt": "2026-11-26T00:00:00Z",
        "files": [],
    }


@pytest.mark.asyncio
async def test_new_book_flows_from_bookorbit_polling_to_discord_delivery(
    integration_setup: tuple[sessionmaker[Session], Server, Library],
) -> None:
    """A baseline is silent; the next source ID becomes exactly one delivered Discord message."""

    factory, server, _library = integration_setup
    source_books = [_book_card(1, "Existing")]

    def bookorbit_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer bok_read_only"
        if request.method == "POST" and request.url.path == "/api/v1/libraries/17/books":
            return httpx.Response(200, json={"items": source_books, "total": len(source_books), "page": 0, "size": 200})
        if request.method == "GET" and request.url.path == "/api/v1/books/2":
            return httpx.Response(200, json=_book_detail(2, "New arrival"))
        return httpx.Response(404)

    polling = BookOrbitPollingService(factory)
    metadata = MetadataRefreshService(factory)
    source_client = BookOrbitClient("https://books.example", "bok_read_only", transport=httpx.MockTransport(bookorbit_handler))
    try:
        baseline = await polling.scan_server(server.id, source_client)
        source_books.append(_book_card(2, "Importing"))
        detected = await polling.scan_server(server.id, source_client)
        metadata_report = await metadata.process_due_events(server.id, source_client, now=datetime.now(UTC) + timedelta(seconds=1))
    finally:
        await source_client.aclose()

    discord_requests: list[httpx.Request] = []

    def discord_handler(request: httpx.Request) -> httpx.Response:
        discord_requests.append(request)
        assert request.url.params["wait"] == "true"
        assert b"New arrival" in request.content
        return httpx.Response(200, json={"id": "discord-message-1"})

    worker = DiscordDeliveryWorker(
        factory,
        StaticWebhookResolver(),
        DefaultEmbedBuilder(factory),
        SimulatedDiscordSender(httpx.MockTransport(discord_handler)),
    )
    delivery_report = await worker.process_once(now=datetime.now(UTC) + timedelta(seconds=2))

    assert baseline.libraries[0].result is not None
    assert baseline.libraries[0].result.events_created == 0
    assert detected.libraries[0].result is not None
    assert detected.libraries[0].result.events_created == 1
    assert metadata_report.released == 1
    assert delivery_report.sent == 1
    assert len(discord_requests) == 1
    with factory() as session:
        event = session.scalar(select(Event))
        item = session.scalar(select(NotificationQueueItem))
        assert event is not None and event.status == EventStatus.COMPLETED
        assert item is not None and item.status == QueueStatus.SENT
        assert item.discord_message_id == "discord-message-1"


@pytest.mark.asyncio
async def test_source_and_discord_outages_preserve_durable_work(
    integration_setup: tuple[sessionmaker[Session], Server, Library],
) -> None:
    """Source 503 is logged as a failed scan and Discord 429 leaves its queue row retryable."""

    factory, server, library = integration_setup
    source_client = BookOrbitClient(
        "https://books.example",
        "bok_read_only",
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"message": "maintenance"})),
    )
    try:
        report = await BookOrbitPollingService(factory).scan_server(server.id, source_client)
    finally:
        await source_client.aclose()

    assert report.libraries[0].error == "BookOrbit library book query request failed (HTTP 503)"
    with factory() as session:
        history = session.scalar(select(ScanHistory))
        assert history is not None and history.status == ScanStatus.FAILED
    with factory.begin() as session:
        # The next complete source observation establishes its silent baseline and then detects a new ID.
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

    def discord_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"retry_after": 5})

    worker = DiscordDeliveryWorker(
        factory,
        StaticWebhookResolver(),
        DefaultEmbedBuilder(factory),
        SimulatedDiscordSender(httpx.MockTransport(discord_handler)),
    )
    delivery_report = await worker.process_once(now=datetime.now(UTC))

    assert delivery_report.retried == 1
    with factory() as session:
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None and item.status == QueueStatus.RETRY
