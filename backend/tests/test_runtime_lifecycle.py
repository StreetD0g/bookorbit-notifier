from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import create_database_engine
from app.main import app


def test_runtime_lifecycle_starts_only_when_explicitly_enabled(monkeypatch, tmp_path: Path) -> None:
    """An enabled, migrated empty database starts and stops the background loop cleanly."""

    database_path = tmp_path / "runtime.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_DATABASE_URL", database_url)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert hasattr(app.state, "runtime_scheduler")
    finally:
        get_settings.cache_clear()
