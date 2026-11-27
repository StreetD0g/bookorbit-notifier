from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher
from app.database.base import Base
from app.database.models import Book, Event, EventStatus, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.schemas.bookorbit import BookOrbitBookDetail
from app.services.configuration import ConfigurationService
from app.services.metadata import MetadataRefreshService


class DetailClient:
    """Deterministic BookOrbit detail source for metadata-wait tests."""

    def __init__(self, detail: BookOrbitBookDetail | None = None, *, error: BookOrbitApiError | None = None) -> None:
        self.detail = detail
        self.error = error
        self.requested_ids: list[int] = []

    async def get_book(self, book_id: int) -> BookOrbitBookDetail:
        self.requested_ids.append(book_id)
        if self.error is not None:
            raise self.error
        assert self.detail is not None
        return self.detail


@pytest.fixture
def metadata_setup(tmp_path: Path) -> tuple[Session, Server, Library, Event]:
    """Create a newly detected event that has one routed destination waiting for metadata."""

    engine = create_engine(f"sqlite:///{tmp_path / 'metadata.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
    library = Library(
        server=server,
        bookorbit_library_id=9,
        name="Books",
        monitored=True,
        metadata_delay_seconds=0,
        metadata_max_wait_seconds=60,
    )
    library.webhooks.append(Webhook(name="Target", url_encrypted="encrypted"))
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
        observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing"), ObservedBook(bookorbit_book_id=2, title="New")],
        scan_complete=True,
    )
    session.commit()
    event = session.scalar(select(Event))
    assert event is not None
    yield session, server, library, event
    session.close()
    engine.dispose()


def _detail(title: str | None) -> BookOrbitBookDetail:
    return BookOrbitBookDetail.model_validate(
        {
            "id": 2,
            "libraryId": 9,
            "libraryName": "Books",
            "title": title,
            "authors": [{"id": 4, "name": "Author", "sortName": None}],
            "genres": [],
            "tags": [],
            "addedAt": "2026-11-26T00:00:00Z",
            "updatedAt": "2026-11-26T00:00:00Z",
            "files": [],
        }
    )


@pytest.mark.asyncio
async def test_metadata_detail_releases_event_and_delivery_when_title_is_present(
    metadata_setup: tuple[Session, Server, Library, Event],
) -> None:
    """The queue stays blocked until a refreshed source detail contains a title."""

    session, server, _library, event = metadata_setup
    now = datetime(2026, 11, 26, tzinfo=UTC)
    event.metadata_not_before_at = now - timedelta(seconds=1)
    event.metadata_deadline_at = now + timedelta(minutes=5)
    session.commit()
    service = MetadataRefreshService(lambda: Session(session.bind))

    report = await service.process_due_events(server.id, DetailClient(_detail("Enriched")), now=now)

    assert report.checked == 1
    assert report.released == 1
    session.refresh(event)
    assert event.status == EventStatus.READY
    queue_item = session.scalar(select(NotificationQueueItem))
    assert queue_item is not None
    assert queue_item.status == QueueStatus.READY
    book = session.scalar(select(Book).where(Book.bookorbit_book_id == 2))
    assert book is not None
    assert book.title == "Enriched"
    assert book.authors_json == ["Author"]


@pytest.mark.asyncio
async def test_metadata_missing_title_retries_until_deadline(metadata_setup: tuple[Session, Server, Library, Event]) -> None:
    """Optional metadata is not required, but a temporarily missing title is retried."""

    session, server, _library, event = metadata_setup
    now = datetime(2026, 11, 26, tzinfo=UTC)
    event.metadata_not_before_at = now - timedelta(seconds=1)
    event.metadata_deadline_at = now + timedelta(minutes=5)
    session.commit()
    service = MetadataRefreshService(lambda: Session(session.bind), retry_seconds=30)

    report = await service.process_due_events(server.id, DetailClient(_detail(None)), now=now)

    assert report.deferred == 1
    session.refresh(event)
    assert event.status == EventStatus.WAITING_FOR_METADATA
    assert event.metadata_attempt_count == 1
    # SQLite returns naive datetimes even for timezone-aware SQLAlchemy columns.
    assert event.metadata_not_before_at == (now + timedelta(seconds=30)).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_metadata_source_failure_releases_available_data_at_deadline(
    metadata_setup: tuple[Session, Server, Library, Event],
) -> None:
    """A persistent source failure cannot block notification delivery forever."""

    session, server, _library, event = metadata_setup
    now = datetime(2026, 11, 26, tzinfo=UTC)
    event.metadata_not_before_at = now - timedelta(seconds=1)
    event.metadata_deadline_at = now
    session.commit()
    service = MetadataRefreshService(lambda: Session(session.bind))

    report = await service.process_due_events(server.id, DetailClient(error=BookOrbitApiError("book detail", 503)), now=now)

    assert report.failed == 1
    assert report.released == 1
    session.refresh(event)
    assert event.status == EventStatus.READY


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_metadata_retry_does_not_overshoot_deadline(metadata_setup, failure: bool) -> None:
    session, server, _library, event = metadata_setup
    now = datetime(2026, 11, 26, tzinfo=UTC)
    event.metadata_not_before_at = now - timedelta(seconds=1)
    event.metadata_deadline_at = now + timedelta(seconds=5)
    session.commit()
    client = DetailClient(error=BookOrbitApiError("book detail", 503)) if failure else DetailClient(_detail(None))
    await MetadataRefreshService(lambda: Session(session.bind), retry_seconds=30).process_due_events(server.id, client, now=now)
    session.refresh(event)
    assert event.metadata_not_before_at == (now + timedelta(seconds=5)).replace(tzinfo=None)


def test_timing_changes_apply_only_to_new_events(metadata_setup) -> None:
    session, server, library, existing_event = metadata_setup
    previous = (existing_event.metadata_not_before_at, existing_event.metadata_deadline_at)
    service = ConfigurationService(lambda: Session(session.bind), SecretCipher(Fernet.generate_key().decode()))
    service.configure_library_metadata(library.id, delay_seconds=15, max_wait_seconds=60)
    session.expire_all()
    assert (existing_event.metadata_not_before_at, existing_event.metadata_deadline_at) == previous
    reconcile_library_inventory(
        session,
        server_id=server.id,
        library_id=library.id,
        observed_books=[
            ObservedBook(bookorbit_book_id=1, title="Existing"),
            ObservedBook(bookorbit_book_id=2, title="New"),
            ObservedBook(bookorbit_book_id=3, title="Later"),
        ],
        scan_complete=True,
    )
    session.commit()
    newest = session.scalars(select(Event).order_by(Event.id.desc())).first()
    assert newest is not None and newest.id != existing_event.id
    assert abs((newest.metadata_not_before_at - newest.detected_at).total_seconds() - 15) < 2
    assert abs((newest.metadata_deadline_at - newest.detected_at).total_seconds() - 60) < 2
