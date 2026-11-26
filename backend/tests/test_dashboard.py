"""Dashboard counts exclude baseline books and use explicit UTC calendar boundaries."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models import Book, Event, EventType, Library, ScanHistory, ScanStatus, Server
from app.services.dashboard import DashboardService


def test_dashboard_counts_only_detected_events_in_utc_windows(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        source = Server(name="Source", base_url="https://internal.example", api_key_encrypted="ciphertext")
        library = Library(server=source, name="Books", bookorbit_library_id=1, monitored=True)
        books = [Book(server=source, library=library, bookorbit_book_id=idx, title=f"Book {idx}") for idx in (1, 2, 3)]
        session.add_all(books)
        session.flush()
        session.add_all(
            [
                Event(
                    server_id=source.id,
                    library_id=library.id,
                    book_id=books[1].id,
                    event_type=EventType.BOOK_ADDED,
                    detected_at=datetime(2026, 11, 25, 12, tzinfo=UTC),
                ),
                Event(
                    server_id=source.id,
                    library_id=library.id,
                    book_id=books[2].id,
                    event_type=EventType.BOOK_ADDED,
                    detected_at=datetime(2026, 11, 26, 12, tzinfo=UTC),
                ),
                ScanHistory(
                    server_id=source.id,
                    library_id=library.id,
                    status=ScanStatus.SUCCEEDED,
                    started_at=datetime(2026, 11, 25, tzinfo=UTC),
                    completed_at=datetime(2026, 11, 25, tzinfo=UTC),
                ),
            ]
        )
    result = DashboardService(factory).summary(now=datetime(2026, 11, 26, 15, tzinfo=UTC))
    assert (result["library_count"], result["monitored_count"], result["book_count"]) == (1, 1, 3)
    assert (result["arrivals_today"], result["arrivals_week"], result["arrivals_month"]) == (1, 2, 2)
    assert result["servers"][0]["id"] == 1
    assert result["servers"][0]["last_library_scan_status"] == ScanStatus.SUCCEEDED
    assert result["servers"][0]["last_library_scan_at"].date().isoformat() == "2026-11-25"
    assert "ciphertext" not in str(result) and "internal.example" not in str(result)
    engine.dispose()


def test_server_overview_reports_latest_library_scan_without_sensitive_errors(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard-status.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="A", base_url="https://private.example", api_key_encrypted="ciphertext")
        no_scans = Server(name="B", base_url="https://private.example", api_key_encrypted="ciphertext", enabled=False)
        library = Library(server=server, name="Books", bookorbit_library_id=1)
        session.add_all([server, no_scans, library])
        session.flush()
        for day, status in [(1, ScanStatus.SUCCEEDED), (2, ScanStatus.FAILED)]:
            session.add(
                ScanHistory(
                    server_id=server.id,
                    library_id=library.id,
                    status=status,
                    started_at=datetime(2026, 1, day, tzinfo=UTC),
                    completed_at=datetime(2026, 1, day, tzinfo=UTC),
                    error_message="private error",
                )
            )
    result = DashboardService(factory).summary(now=datetime(2026, 1, 3, tzinfo=UTC))
    first, second = result["servers"]
    assert first["last_library_scan_status"] == ScanStatus.FAILED
    assert first["last_library_scan_at"].day == 2
    assert second["enabled"] is False and second["last_library_scan_status"] is None
    assert "private" not in str(result) and "ciphertext" not in str(result)
    engine.dispose()
