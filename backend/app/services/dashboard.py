"""Read-only dashboard aggregates based on notifier-owned state."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Book, Event, EventType, Library, ScanHistory, ScanStatus, Server

type SessionFactory = Callable[[], Session]


class DashboardService:
    """Summarize persisted data without guessing network availability."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def summary(self, *, now: datetime | None = None) -> dict:
        """Calendar periods use UTC and count detected arrivals, not baseline books."""

        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("Dashboard timestamp must include a timezone")
        timestamp = timestamp.astimezone(UTC)
        today = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        week = today - timedelta(days=today.weekday())
        month = today.replace(day=1)
        with self._session_factory() as session:
            library_count = session.scalar(select(func.count(Library.id))) or 0
            monitored_count = session.scalar(select(func.count(Library.id)).where(Library.monitored.is_(True))) or 0
            book_count = session.scalar(select(func.count(Book.id))) or 0
            counts = {}
            for label, start in (("today", today), ("week", week), ("month", month)):
                counts[label] = (
                    session.scalar(
                        select(func.count(Event.id)).where(
                            Event.event_type == EventType.BOOK_ADDED, Event.detected_at >= start, Event.detected_at <= timestamp
                        )
                    )
                    or 0
                )
            last_success = session.scalar(select(func.max(ScanHistory.completed_at)).where(ScanHistory.status == ScanStatus.SUCCEEDED))
            # ScanHistory is per library, so expose it as such rather than claiming
            # that a single row proves the whole server is currently reachable.
            recent_scan_id = (
                select(ScanHistory.id)
                .where(ScanHistory.server_id == Server.id)
                .order_by(ScanHistory.completed_at.desc(), ScanHistory.id.desc())
                .limit(1)
                .correlate(Server)
                .scalar_subquery()
            )
            servers = session.execute(
                select(Server.id, Server.name, Server.enabled, ScanHistory.status, ScanHistory.completed_at)
                .outerjoin(ScanHistory, ScanHistory.id == recent_scan_id)
                .order_by(Server.name, Server.id)
            ).all()
            return {
                "library_count": library_count,
                "monitored_count": monitored_count,
                "book_count": book_count,
                "arrivals_today": counts["today"],
                "arrivals_week": counts["week"],
                "arrivals_month": counts["month"],
                "last_successful_scan": last_success,
                "servers": [
                    {
                        "id": server.id,
                        "name": server.name,
                        "enabled": server.enabled,
                        "last_library_scan_status": server.status,
                        "last_library_scan_at": server.completed_at,
                    }
                    for server in servers
                ],
                "timezone": "UTC",
            }
