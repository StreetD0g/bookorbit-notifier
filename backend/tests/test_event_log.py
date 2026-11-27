"""Operational log retention and privacy are enforced independently of the UI."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import create_database_engine
from app.main import app
from app.services.event_log import EventLog


def test_event_log_rotates_filters_and_rejects_arbitrary_input(tmp_path: Path) -> None:
    log = EventLog(tmp_path, max_bytes=250, backups=2)
    try:
        for index in range(8):
            log.write("scan_failed" if index % 2 else "scan_succeeded", server_id=1, library_id=2)
        files = sorted(tmp_path.glob("events.jsonl*"))
        assert len(files) <= 3 and all(path.stat().st_size <= 250 for path in files)
        entries = log.list_entries(level="ERROR", server_id=1, library_id=2, limit=1)
        assert len(entries["items"]) == 1 and entries["items"][0]["code"] == "scan_failed"
        assert entries["has_more"] is True
        page_two = log.list_entries(level="ERROR", server_id=1, library_id=2, limit=1, offset=1)
        assert len(page_two["items"]) == 1
        assert entries["items"][0]["at"] > page_two["items"][0]["at"]
        assert log.list_entries(server_id=2)["items"] == []
        assert log.list_entries(from_date=date.today() + timedelta(days=2))["items"] == []
        with pytest.raises(ValueError):
            log.write("arbitrary-secret")
        with pytest.raises(ValueError):
            log.write("scan_failed", server_id=True)
    finally:
        log.close()


def test_log_reader_discards_unknown_or_sensitive_fields(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    now = datetime.now(UTC).isoformat()
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                "not json with secret",
                json.dumps(
                    {"at": now, "level": "INFO", "code": "runtime_started", "server_id": None, "library_id": None, "token": "secret"}
                ),
                json.dumps({"at": now, "level": "INFO", "code": "secret", "server_id": None, "library_id": None}),
            ]
        ),
        encoding="utf-8",
    )
    try:
        result = log.list_entries()
        assert len(result["items"]) == 1
        assert "secret" not in str(result)
        assert set(result["items"][0]) == {"at", "level", "code", "server_id", "library_id"}
    finally:
        log.close()


def test_configured_log_is_available_through_admin_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real application owns the log handler for its entire lifespan."""

    url = f"sqlite:///{(tmp_path / 'admin.db').as_posix()}"
    engine = create_database_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_DATABASE_URL", url)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ENABLED", "true")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_RUNTIME_ENABLED", "false")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ORIGIN", "https://notifier.example")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_SETUP_TOKEN", "fixture-setup-token-that-is-long-enough")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_LOG_DIRECTORY", str(tmp_path / "logs"))
    get_settings.cache_clear()
    try:
        with TestClient(app, base_url="https://notifier.example") as client:
            app.state.event_log.write("runtime_started")
            setup = client.post(
                "/api/v1/admin/setup",
                headers={"origin": "https://notifier.example", "x-setup-token": "fixture-setup-token-that-is-long-enough"},
                json={"password": "fixture password sufficiently long"},
            )
            assert setup.status_code == 201
            login = client.post(
                "/api/v1/admin/login",
                headers={"origin": "https://notifier.example"},
                json={"password": "fixture password sufficiently long"},
            )
            assert login.status_code == 200
            result = client.get("/api/v1/admin/logs").json()
            assert result["enabled"] is True and result["items"][0]["code"] == "runtime_started"
    finally:
        get_settings.cache_clear()
