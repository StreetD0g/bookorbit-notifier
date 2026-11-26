"""A dependency-light periodic scheduler for the single-container MVP runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Server
from app.queue.worker import DeliveryWorkerReport
from app.scanner.polling import ServerScanReport
from app.services.metadata import MetadataRefreshReport

type SessionFactory = Callable[[], Session]

logger = logging.getLogger(__name__)


class SourceClientFactory(Protocol):
    """Open an authenticated BookOrbit client only for one scheduled server pass."""

    def connect(self, server_id: int) -> AbstractAsyncContextManager[object]:
        """Return an async context manager exposing one source client."""


class PollingService(Protocol):
    """Polling interface kept small so the scheduler can be tested in isolation."""

    async def scan_server(self, server_id: int, client: object) -> ServerScanReport:
        """Run a complete source scan for one server."""


class MetadataService(Protocol):
    """Metadata interface executed after a source scan with the same client."""

    async def process_due_events(self, server_id: int, client: object, *, now: datetime) -> MetadataRefreshReport:
        """Refresh metadata that is eligible at this scheduler time."""


class DeliveryService(Protocol):
    """Outbox interface executed every scheduler tick, even when no scan is due."""

    async def process_once(self, *, now: datetime) -> DeliveryWorkerReport:
        """Deliver a bounded eligible outbox batch."""


@dataclass(frozen=True, slots=True)
class ScheduledServerReport:
    """One server's result from a scheduler tick, with redacted error context."""

    server_id: int
    scan: ServerScanReport | None
    metadata: MetadataRefreshReport | None
    error: str | None


@dataclass(frozen=True, slots=True)
class SchedulerTickReport:
    """Aggregate status for monitoring without leaking source/destination secrets."""

    servers: tuple[ScheduledServerReport, ...]
    delivery: DeliveryWorkerReport


class RuntimeScheduler:
    """Schedule enabled servers by their persisted interval in one application process."""

    def __init__(
        self,
        session_factory: SessionFactory,
        client_factory: SourceClientFactory,
        polling_service: PollingService,
        metadata_service: MetadataService,
        delivery_service: DeliveryService,
    ) -> None:
        self._session_factory = session_factory
        self._client_factory = client_factory
        self._polling_service = polling_service
        self._metadata_service = metadata_service
        self._delivery_service = delivery_service
        self._next_due: dict[int, datetime] = {}

    async def run_once(self, *, now: datetime | None = None, force_server_id: int | None = None) -> SchedulerTickReport:
        """Run due scans and the outbox once; `force_server_id` is the manual trigger hook."""

        timestamp = now or datetime.now(UTC)
        targets = self._due_servers(timestamp, force_server_id)
        reports: list[ScheduledServerReport] = []
        for server_id, interval_seconds in targets:
            reports.append(await self._run_server(server_id, interval_seconds, timestamp))
        delivery = await self._delivery_service.process_once(now=timestamp)
        return SchedulerTickReport(servers=tuple(reports), delivery=delivery)

    async def run_forever(self, stop_event: asyncio.Event, *, tick_seconds: float = 1.0) -> None:
        """Run until application shutdown; tick frequently while server intervals remain configurable."""

        if tick_seconds <= 0:
            raise ValueError("Scheduler tick interval must be positive")
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception as error:
                # A transient database/transport failure must not permanently stop polling.
                # Keep raw adapter messages out of logs because they may contain credentials.
                logger.warning("Runtime scheduler tick failed (%s)", type(error).__name__)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=tick_seconds)
            except TimeoutError:
                continue

    def _due_servers(self, now: datetime, force_server_id: int | None) -> list[tuple[int, int]]:
        """Read enabled server intervals and evict disabled/removed entries from memory."""

        with self._session_factory() as session:
            rows = session.execute(select(Server.id, Server.scan_interval_seconds).where(Server.enabled.is_(True))).all()
        configured_ids = {int(row.id) for row in rows}
        self._next_due = {server_id: due for server_id, due in self._next_due.items() if server_id in configured_ids}
        targets: list[tuple[int, int]] = []
        for row in rows:
            server_id = int(row.id)
            interval_seconds = max(1, int(row.scan_interval_seconds))
            if force_server_id is not None and server_id != force_server_id:
                continue
            if force_server_id == server_id or self._next_due.get(server_id, now) <= now:
                targets.append((server_id, interval_seconds))
        return targets

    async def _run_server(self, server_id: int, interval_seconds: int, now: datetime) -> ScheduledServerReport:
        """Run source work with a short-lived client and schedule the next regular pass."""

        try:
            async with self._client_factory.connect(server_id) as client:
                scan = await self._polling_service.scan_server(server_id, client)
                metadata = await self._metadata_service.process_due_events(server_id, client, now=now)
        except Exception as error:
            # Adapters must not expose raw messages: URLs and authentication details are sensitive.
            report = ScheduledServerReport(
                server_id=server_id,
                scan=None,
                metadata=None,
                error=f"Server processing failed ({type(error).__name__})",
            )
        else:
            report = ScheduledServerReport(server_id=server_id, scan=scan, metadata=metadata, error=None)
        self._next_due[server_id] = now + timedelta(seconds=interval_seconds)
        return report
