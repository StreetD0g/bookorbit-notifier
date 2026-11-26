"""SQLite engine setup with the durability settings required by the scanner/outbox."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str) -> Engine:
    """Create an engine and apply SQLite pragmas for every new connection.

    WAL permits readers while a short source-detection transaction writes state.
    Foreign-key enforcement is off by default in SQLite, so it is enabled per
    connection rather than assumed from the schema alone.
    """

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
        _configure_sqlite(engine)
    return engine


def _configure_sqlite(engine: Engine) -> None:
    """Register pragmas once for this engine without mutating global SQLAlchemy state."""

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    """Return an explicit transactional-session factory for workers and tests."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
