"""Bridge verified BookOrbit pages into atomic, persistent library reconciliation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Library, Server
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.scanner.reconcile import ObservedBook, ReconciliationResult, reconcile_library_inventory, record_failed_scan
from app.schemas.bookorbit import BookOrbitBookCard

type SessionFactory = Callable[[], Session]


class InventoryClient(Protocol):
    """The polling dependency needed by reconciliation, kept narrow for testability."""

    def iter_library_books(self, library_id: int) -> AsyncIterator[BookOrbitBookCard]:
        """Yield every current card from one accessible BookOrbit library."""


@dataclass(frozen=True, slots=True)
class LibraryScanReport:
    """Result for one monitored library, suitable for scheduler/status reporting."""

    library_id: int
    source_library_id: int
    result: ReconciliationResult | None
    error: str | None


@dataclass(frozen=True, slots=True)
class ServerScanReport:
    """All library outcomes from an exclusive scan of one BookOrbit server."""

    server_id: int
    libraries: tuple[LibraryScanReport, ...]


class BookOrbitPollingService:
    """Fetch BookOrbit inventories without holding a SQLite write transaction open.

    The service does network I/O before beginning the short reconciliation transaction.
    A per-server async lock protects against overlapping scheduler/manual scans in the
    same process; the future distributed deployment remains intentionally out of scope.
    """

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._server_locks: dict[int, asyncio.Lock] = {}

    async def scan_server(self, server_id: int, client: InventoryClient) -> ServerScanReport:
        """Scan every enabled monitored library visible in stored configuration."""

        lock = self._server_locks.setdefault(server_id, asyncio.Lock())
        async with lock:
            targets = self._load_targets(server_id)
            reports = [await self._scan_library(server_id, target_id, source_id, client) for target_id, source_id in targets]
            return ServerScanReport(server_id=server_id, libraries=tuple(reports))

    def _load_targets(self, server_id: int) -> list[tuple[int, int]]:
        """Read the configured monitor set without retaining ORM state through I/O."""

        with self._session_factory() as session:
            server = session.scalar(select(Server).where(Server.id == server_id, Server.enabled.is_(True)))
            if server is None:
                raise ValueError("Server is missing or disabled")
            rows = session.execute(
                select(Library.id, Library.bookorbit_library_id).where(Library.server_id == server_id, Library.monitored.is_(True))
            ).all()
        return [(int(row.id), int(row.bookorbit_library_id)) for row in rows]

    async def _scan_library(
        self,
        server_id: int,
        library_id: int,
        source_library_id: int,
        client: InventoryClient,
    ) -> LibraryScanReport:
        """Keep useful pages from a failed inventory as a partial, non-removal scan."""

        observed: list[ObservedBook] = []
        try:
            async for card in client.iter_library_books(source_library_id):
                observed.append(_observed_book(card))
        except BookOrbitApiError as error:
            return self._persist_partial_or_failed_scan(server_id, library_id, source_library_id, observed, str(error))

        with self._session_factory() as session:
            with session.begin():
                result = reconcile_library_inventory(
                    session,
                    server_id=server_id,
                    library_id=library_id,
                    observed_books=observed,
                    scan_complete=True,
                )
        return LibraryScanReport(library_id=library_id, source_library_id=source_library_id, result=result, error=None)

    def _persist_partial_or_failed_scan(
        self,
        server_id: int,
        library_id: int,
        source_library_id: int,
        observed: list[ObservedBook],
        error: str,
    ) -> LibraryScanReport:
        """Persist prior pages as partial only after a baseline exists; never lose known arrivals."""

        with self._session_factory() as session:
            with session.begin():
                if observed:
                    result = reconcile_library_inventory(
                        session,
                        server_id=server_id,
                        library_id=library_id,
                        observed_books=observed,
                        scan_complete=False,
                        incomplete_reason=error,
                    )
                else:
                    record_failed_scan(session, server_id=server_id, library_id=library_id, error_message=error)
                    result = None
        return LibraryScanReport(library_id=library_id, source_library_id=source_library_id, result=result, error=error)


def _observed_book(card: BookOrbitBookCard) -> ObservedBook:
    """Copy only non-secret source metadata used for detection and later enrichment."""

    return ObservedBook(
        bookorbit_book_id=card.id,
        title=card.title,
        authors=card.authors,
        source_added_at=card.added_at,
        source_updated_at=card.updated_at,
        metadata=card.model_dump(mode="json", by_alias=True),
    )
