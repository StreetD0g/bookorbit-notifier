from pathlib import Path

from app.database.session import create_database_engine


def test_sqlite_engine_enables_foreign_keys_and_wal(tmp_path: Path) -> None:
    """Connection setup satisfies the persistence guarantees before migrations run."""

    engine = create_database_engine(f"sqlite:///{tmp_path / 'notifier.db'}")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
    finally:
        engine.dispose()
