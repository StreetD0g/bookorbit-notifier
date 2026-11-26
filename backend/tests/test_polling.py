from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import Event, Library, ScanHistory, ScanStatus, Server
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.scanner.polling import BookOrbitPollingService
from app.schemas.bookorbit import BookOrbitBookCard


class FakeBookOrbitClient:
    """Source fixture that simulates paginated results without network access."""

    def __init__(self, cards: list[BookOrbitBookCard], *, fail_after: int | None = None) -> None:
        self.cards = cards
        self.fail_after = fail_after
        self.queried_library_ids: list[int] = []

    async def iter_library_books(self, library_id: int) -> AsyncIterator[BookOrbitBookCard]:
        self.queried_library_ids.append(library_id)
        for index, card in enumerate(self.cards):
            if self.fail_after is not None and index == self.fail_after:
                raise BookOrbitApiError("library book query", 504)
            yield card


@pytest.fixture
def scan_setup(tmp_path: Path) -> tuple[sessionmaker[Session], Server, Library]:
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Test server", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, bookorbit_library_id=19, name="Books", monitored=True)
        session.add_all([server, library])
    return factory, server, library


def _card(book_id: int, title: str = "Example") -> BookOrbitBookCard:
    return BookOrbitBookCard.model_validate(
        {"id": book_id, "libraryId": 19, "title": title, "authors": ["Author"], "files": [], "addedAt": "2026-11-26T00:00:00Z"}
    )


@pytest.mark.asyncio
async def test_polling_service_creates_baseline_then_detects_new_source_id(
    scan_setup: tuple[sessionmaker[Session], Server, Library],
) -> None:
    """Pagination feeds the same silent-baseline and new-arrival rules as manual scans."""

    factory, server, library = scan_setup
    polling = BookOrbitPollingService(factory)
    first_source = FakeBookOrbitClient([_card(1)])
    first = await polling.scan_server(server.id, first_source)

    second_source = FakeBookOrbitClient([_card(1), _card(2, "New")])
    second = await polling.scan_server(server.id, second_source)

    assert first_source.queried_library_ids == [19]
    assert first.libraries[0].result is not None
    assert first.libraries[0].result.events_created == 0
    assert second.libraries[0].result is not None
    assert second.libraries[0].result.events_created == 1
    with factory() as session:
        assert session.scalar(select(func.count(Event.id))) == 1
        persisted_library = session.get(Library, library.id)
        assert persisted_library is not None
        assert persisted_library.baseline_completed_at is not None


@pytest.mark.asyncio
async def test_polling_service_records_partial_scan_when_later_page_fails(
    scan_setup: tuple[sessionmaker[Session], Server, Library],
) -> None:
    """Already returned pages remain useful and no source book is treated as removed."""

    factory, server, _library = scan_setup
    polling = BookOrbitPollingService(factory)
    report = await polling.scan_server(server.id, FakeBookOrbitClient([_card(1), _card(2)], fail_after=1))

    assert report.libraries[0].error == "BookOrbit library book query request failed (HTTP 504)"
    assert report.libraries[0].result is not None
    assert report.libraries[0].result.scan_status == ScanStatus.PARTIAL
    with factory() as session:
        history = session.scalar(select(ScanHistory))
        assert history is not None
        assert history.status == ScanStatus.PARTIAL
