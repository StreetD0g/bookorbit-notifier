from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import Server
from app.queue.worker import DeliveryWorkerReport
from app.scanner.polling import ServerScanReport
from app.scheduler.runtime import RuntimeScheduler
from app.services.metadata import MetadataRefreshReport


class ClientFactory:
    """Records scheduler client lifetime without connecting to a real BookOrbit server."""

    def __init__(self) -> None:
        self.connected_server_ids: list[int] = []

    @asynccontextmanager
    async def connect(self, server_id: int):
        self.connected_server_ids.append(server_id)
        yield object()


class Polling:
    """Records server scans for interval and manual-trigger assertions."""

    def __init__(self) -> None:
        self.server_ids: list[int] = []

    async def scan_server(self, server_id: int, _client: object) -> ServerScanReport:
        self.server_ids.append(server_id)
        return ServerScanReport(server_id=server_id, libraries=())


class Metadata:
    """Records same-client metadata passes."""

    def __init__(self) -> None:
        self.server_ids: list[int] = []

    async def process_due_events(self, server_id: int, _client: object, *, now: datetime) -> MetadataRefreshReport:
        self.server_ids.append(server_id)
        return MetadataRefreshReport(checked=0, released=0, deferred=0, failed=0)


class Delivery:
    """Records outbox ticks even when no source scan is due."""

    def __init__(self) -> None:
        self.calls = 0

    async def process_once(self, *, now: datetime) -> DeliveryWorkerReport:
        self.calls += 1
        return DeliveryWorkerReport(recovered_stale=0, claimed=0, sent=0, retried=0, failed=0)


@pytest.fixture
def scheduler_setup(tmp_path: Path) -> tuple[sessionmaker[Session], Server]:
    engine = create_engine(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted", scan_interval_seconds=60)
        session.add(server)
    return factory, server


@pytest.mark.asyncio
async def test_scheduler_observes_server_interval_and_manual_trigger(
    scheduler_setup: tuple[sessionmaker[Session], Server],
) -> None:
    """Regular ticks respect stored intervals while force_server_id bypasses only its own due time."""

    factory, server = scheduler_setup
    clients = ClientFactory()
    polling = Polling()
    metadata = Metadata()
    delivery = Delivery()
    scheduler = RuntimeScheduler(factory, clients, polling, metadata, delivery)
    start = datetime(2026, 11, 26, tzinfo=UTC)

    first = await scheduler.run_once(now=start)
    snapshot = scheduler.scheduled_scans()
    assert snapshot == {server.id: start + timedelta(seconds=60)}
    snapshot.clear()
    assert scheduler.scheduled_scans() == {server.id: start + timedelta(seconds=60)}
    second = await scheduler.run_once(now=start + timedelta(seconds=30))
    forced = await scheduler.run_once(now=start + timedelta(seconds=31), force_server_id=server.id)

    assert len(first.servers) == 1
    assert second.servers == ()
    assert len(forced.servers) == 1
    assert polling.server_ids == [server.id, server.id]
    assert metadata.server_ids == [server.id, server.id]
    assert clients.connected_server_ids == [server.id, server.id]
    assert delivery.calls == 3


@pytest.mark.asyncio
async def test_manual_scan_does_not_trigger_unrelated_delivery(scheduler_setup: tuple[sessionmaker[Session], Server]) -> None:
    factory, server = scheduler_setup
    polling, delivery = Polling(), Delivery()
    scheduler = RuntimeScheduler(factory, ClientFactory(), polling, Metadata(), delivery)
    report = await scheduler.run_manual_scan(server.id, now=datetime(2026, 11, 26, tzinfo=UTC))
    assert report.server_id == server.id and report.error is None
    assert polling.server_ids == [server.id] and delivery.calls == 0
    with pytest.raises(ValueError, match="missing or disabled"):
        await scheduler.run_manual_scan(999)


@pytest.mark.asyncio
async def test_scheduler_logs_only_safe_event_codes_and_survives_log_failure(scheduler_setup) -> None:
    factory, server = scheduler_setup

    class FailedPolling:
        async def scan_server(self, server_id, _client):
            raise RuntimeError("secret webhook or API key")

    class CaptureLog:
        def __init__(self):
            self.entries = []
            self.fail = False

        def write(self, code, *, server_id=None, library_id=None):
            if self.fail:
                raise OSError("private filesystem details")
            self.entries.append((code, server_id, library_id))

    log = CaptureLog()
    scheduler = RuntimeScheduler(factory, ClientFactory(), FailedPolling(), Metadata(), Delivery(), event_log=log)
    result = await scheduler.run_once(now=datetime(2026, 11, 26, tzinfo=UTC))
    assert result.servers[0].error == "Server processing failed (RuntimeError)"
    assert log.entries == [("server_failed", server.id, None)]
    assert "secret" not in str(log.entries)
    log.fail = True
    result = await scheduler.run_once(now=datetime(2026, 11, 26, tzinfo=UTC) + timedelta(seconds=60))
    assert len(result.servers) == 1
