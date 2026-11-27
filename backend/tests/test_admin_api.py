"""Exercise the administrator surface through HTTP, including failure paths."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import Base
from app.database.models import (
    Book,
    Event,
    EventType,
    Library,
    NotificationQueueItem,
    QueueStatus,
    ScanHistory,
    ScanStatus,
    SenderProfileConfig,
    Server,
    Webhook,
)
from app.database.session import create_database_engine
from app.main import app
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.providers.notifications.discord.client import DiscordDeliveryError, DiscordWebhookOriginal
from app.providers.notifications.discord.sender_profile import BUNDLED_LOGO_URL
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.schemas.bookorbit import BookOrbitIdentity, BookOrbitLibrary, CoverImage

ORIGIN = "https://notifier.example"
SETUP_TOKEN = "setup-token-for-testing-only-123456789"
PASSWORD = "test password for admin"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'admin.db').as_posix()}"
    engine = create_database_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ENABLED", "true")
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ORIGIN", ORIGIN)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_SETUP_TOKEN", SETUP_TOKEN)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        with TestClient(app, base_url=ORIGIN) as test_client:
            yield test_client, engine
    finally:
        get_settings.cache_clear()
        engine.dispose()


def setup_and_login(client: TestClient) -> str:
    response = client.post("/api/v1/admin/setup", headers={"origin": ORIGIN, "x-setup-token": SETUP_TOKEN}, json={"password": PASSWORD})
    assert response.status_code == 201
    response = client.post("/api/v1/admin/login", headers={"origin": ORIGIN}, json={"password": PASSWORD})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert "Secure" in response.headers.get_list("set-cookie")[0]
    assert "SameSite=strict" in response.headers.get_list("set-cookie")[0]
    return client.cookies.get("bookorbit_csrf")


def test_library_metadata_timing_is_authenticated_validated_and_persisted(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="private")
        library = Library(server=server, name="Library", bookorbit_library_id=1)
        session.add(library)
        session.commit()
        library_id = library.id
    url = f"/api/v1/admin/libraries/{library_id}/metadata"
    valid = {"delay_seconds": 15, "max_wait_seconds": 60}
    assert http.put(url, headers={"origin": ORIGIN}, json=valid).status_code == 401
    csrf = setup_and_login(http)
    assert http.put(url, headers={"origin": ORIGIN}, json=valid).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.put(url, headers=headers, json=valid).status_code == 200
    for invalid in [
        {"delay_seconds": 61, "max_wait_seconds": 60},
        {"delay_seconds": -1, "max_wait_seconds": 60},
        {"delay_seconds": 0, "max_wait_seconds": 604801},
        {"delay_seconds": True, "max_wait_seconds": 60},
    ]:
        assert http.put(url, headers=headers, json=invalid).status_code in (400, 422)
    assert http.put("/api/v1/admin/libraries/99999/metadata", headers=headers, json=valid).status_code == 400
    result = http.get("/api/v1/admin/libraries").json()
    assert result[0]["metadata_delay_seconds"] == 15
    assert result[0]["metadata_max_wait_seconds"] == 60
    assert "private" not in str(result)


def test_remove_unused_webhook_requires_confirmation_and_preserves_delivery_history(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="secret")
        library = Library(server=server, name="Books", bookorbit_library_id=1)
        unused = Webhook(name="Unused", url_encrypted="secret", enabled=False)
        active = Webhook(name="Active", url_encrypted="secret", enabled=True)
        used = Webhook(name="Used", url_encrypted="secret", enabled=False)
        library.webhooks.extend([unused, active, used])
        book = Book(server=server, library=library, bookorbit_book_id=1, title="Existing")
        event = Event(book=book, server_id=1, library_id=1, event_type=EventType.BOOK_ADDED)
        used.deliveries.append(NotificationQueueItem(event=event, status=QueueStatus.SENT))
        session.add_all([server, library, book])
        session.flush()
        unused_id, active_id, used_id = unused.id, active.id, used.id
        session.add(SenderProfileConfig(scope_key=f"webhook:{unused_id}", username_choice="inherit", avatar_choice="inherit"))
        session.commit()
    url = f"/api/v1/admin/webhooks/{unused_id}"
    assert http.request("DELETE", url, headers={"origin": ORIGIN}, json={"confirmed": True}).status_code == 401
    csrf = setup_and_login(http)
    assert http.request("DELETE", url, headers={"origin": ORIGIN}, json={"confirmed": True}).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.request("DELETE", url, headers=headers, json={"confirmed": "true"}).status_code == 422
    assert http.request("DELETE", url, headers=headers, json={"confirmed": False}).status_code == 409
    assert http.request("DELETE", f"/api/v1/admin/webhooks/{active_id}", headers=headers, json={"confirmed": True}).status_code == 409
    assert http.request("DELETE", f"/api/v1/admin/webhooks/{used_id}", headers=headers, json={"confirmed": True}).status_code == 409
    assert http.request("DELETE", url, headers=headers, json={"confirmed": True}).status_code == 200
    assert http.request("DELETE", url, headers=headers, json={"confirmed": True}).status_code == 409
    with Session(engine) as session:
        assert session.get(Webhook, unused_id) is None
        assert session.get(SenderProfileConfig, f"webhook:{unused_id}") is None
        assert session.get(Webhook, used_id) is not None
        assert session.scalar(select(NotificationQueueItem)) is not None
        assert {webhook.id for webhook in session.get(Library, 1).webhooks} == {active_id, used_id}


def test_setup_login_cookie_csrf_and_logout(client) -> None:
    http, _engine = client
    assert http.get("/api/v1/admin/notifications/summary").status_code == 401
    assert http.get("/api/v1/admin/dashboard").status_code == 401
    assert http.get("/admin").status_code == 200
    assert "frame-ancestors 'none'" in http.get("/admin").headers["content-security-policy"]
    assert http.get("/admin-assets/admin.js").status_code == 200
    assert http.get("/admin-assets/admin.css").status_code == 200
    stylesheet = http.get("/admin-assets/admin.css")
    assert stylesheet.headers["cache-control"] == "no-cache"
    revalidated = http.get("/admin-assets/admin.css", headers={"if-none-match": stylesheet.headers["etag"]})
    assert revalidated.status_code == 304 and revalidated.headers["cache-control"] == "no-cache"
    assert http.get("/admin-assets/admin.js").headers["cache-control"] == "no-cache"
    assert ':root[data-theme="light"]' in http.get("/admin-assets/admin.css").text
    assert (
        http.post(
            "/api/v1/admin/setup", headers={"origin": "https://evil.example", "x-setup-token": SETUP_TOKEN}, json={"password": PASSWORD}
        ).status_code
        == 403
    )
    assert (
        http.post("/api/v1/admin/setup", headers={"origin": ORIGIN, "x-setup-token": "wrong"}, json={"password": PASSWORD}).status_code
        == 403
    )
    csrf = setup_and_login(http)
    assert (
        http.post("/api/v1/admin/setup", headers={"origin": ORIGIN, "x-setup-token": SETUP_TOKEN}, json={"password": PASSWORD}).status_code
        == 400
    )
    assert http.get("/api/v1/admin/notifications/summary").json()["queued"] == 0
    assert http.get("/api/v1/admin/dashboard").json()["book_count"] == 0
    assert http.post("/api/v1/admin/logout", headers={"origin": ORIGIN}).status_code == 401
    assert http.post("/api/v1/admin/logout", headers={"origin": "https://evil.example", "x-csrf-token": csrf}).status_code == 403
    assert http.post("/api/v1/admin/logout", headers={"origin": ORIGIN, "x-csrf-token": csrf}).status_code == 200
    assert http.get("/api/v1/admin/notifications/summary").status_code == 401


def test_dashboard_reports_runtime_schedule_only_for_enabled_servers(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    setup_and_login(http)
    with Session(engine) as session:
        session.add_all(
            [
                Server(name="Active", base_url="https://books.example", api_key_encrypted="secret", enabled=True),
                Server(name="Disabled", base_url="https://books.example", api_key_encrypted="secret", enabled=False),
            ]
        )
        session.commit()
    without_runtime = http.get("/api/v1/admin/dashboard").json()
    assert without_runtime["runtime_enabled"] is False
    assert all(server["next_scan_at"] is None for server in without_runtime["servers"])

    class Scheduled:
        def scheduled_scans(self):
            return {1: "scheduled", 2: "stale disabled"}

    monkeypatch.setitem(app.state._state, "runtime_scheduler", Scheduled())
    result = http.get("/api/v1/admin/dashboard").json()
    assert result["runtime_enabled"] is True
    assert [server["next_scan_at"] for server in result["servers"]] == ["scheduled", None]
    assert "secret" not in str(result)


def test_operational_log_endpoint_is_authenticated_and_filtered(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.services.event_log import EventLog

    http, _engine = client
    assert http.get("/api/v1/admin/logs").status_code == 401
    setup_and_login(http)
    assert http.get("/api/v1/admin/logs").json() == {"enabled": False, "items": [], "has_more": False}
    log = EventLog(tmp_path / "events")
    try:
        log.write("scan_failed", server_id=1, library_id=2)
        log.write("runtime_started")
        monkeypatch.setitem(app.state._state, "event_log", log)
        result = http.get("/api/v1/admin/logs?level=ERROR&server_id=1&library_id=2")
        assert result.status_code == 200 and result.json()["items"][0]["code"] == "scan_failed"
        assert http.get("/api/v1/admin/logs?level=INVALID").status_code == 422
        assert http.get("/api/v1/admin/logs?from_date=2026-02-02&to_date=2026-01-01").status_code == 400
        assert http.get("/api/v1/admin/logs?limit=101").status_code == 422
    finally:
        log.close()


def test_admin_changes_create_redacted_filtered_operational_events(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.services.event_log import EventLog

    http, engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://private.example", api_key_encrypted="secret-value", enabled=True)
        library = Library(server=server, name="Books", bookorbit_library_id=4)
        session.add(library)
        session.commit()
        server_id, library_id = server.id, library.id
    log = EventLog(tmp_path / "events")
    monkeypatch.setitem(app.state._state, "event_log", log)
    try:
        csrf = setup_and_login(http)
        headers = {"origin": ORIGIN, "x-csrf-token": csrf}
        path = f"/api/v1/admin/servers/{server_id}/enabled"
        assert http.put(path, headers=headers, json={"enabled": False}).status_code == 200
        assert http.put(path, headers=headers, json={"enabled": False}).status_code == 200
        metadata_path = f"/api/v1/admin/libraries/{library_id}/metadata"
        assert http.put(metadata_path, headers=headers, json={"delay_seconds": 60, "max_wait_seconds": 30}).status_code == 400
        assert http.put(metadata_path, headers=headers, json={"delay_seconds": 30, "max_wait_seconds": 60}).status_code == 200
        response = http.get(f"/api/v1/admin/logs?server_id={server_id}")
        assert [entry["code"] for entry in response.json()["items"]] == ["library_metadata_updated", "server_disabled"]
        filtered = http.get(f"/api/v1/admin/logs?library_id={library_id}").json()["items"]
        assert len(filtered) == 1 and filtered[0]["server_id"] == server_id
        assert "secret-value" not in response.text and "private.example" not in response.text
        monkeypatch.setattr(log, "write", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("private")))
        assert http.put(path, headers=headers, json={"enabled": True}).status_code == 200
        assert http.put(metadata_path, headers=headers, json={"delay_seconds": 10, "max_wait_seconds": 60}).status_code == 200
    finally:
        log.close()


def test_scan_history_is_authenticated_paginated_filtered_and_redacted(client) -> None:
    http, engine = client
    assert http.get("/api/v1/admin/scan-history").status_code == 401
    setup_and_login(http)
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://private.example", api_key_encrypted="key-secret")
        library = Library(server=server, name="Library", bookorbit_library_id=1)
        session.add_all([server, library])
        session.flush()
        for day, status in [(1, ScanStatus.SUCCEEDED), (2, ScanStatus.PARTIAL), (3, ScanStatus.FAILED)]:
            session.add(
                ScanHistory(
                    server_id=server.id,
                    library_id=library.id,
                    status=status,
                    started_at=datetime(2026, 1, day, tzinfo=UTC),
                    completed_at=datetime(2026, 1, day, tzinfo=UTC),
                    books_seen=10,
                    books_added=2,
                    error_message="webhook-secret",
                )
            )
        session.commit()
    response = http.get("/api/v1/admin/scan-history?limit=2")
    assert response.status_code == 200
    assert [row["status"] for row in response.json()["items"]] == ["FAILED", "PARTIAL"]
    assert response.json()["has_more"] is True
    assert all(secret not in response.text for secret in ["key-secret", "webhook-secret", "private.example"])
    assert http.get("/api/v1/admin/scan-history?limit=2&offset=2").json()["has_more"] is False
    filtered = http.get(
        "/api/v1/admin/scan-history?scan_status=PARTIAL&server_id=1&library_id=1&from_date=2026-01-02&to_date=2026-01-02"
    ).json()
    assert len(filtered["items"]) == 1 and filtered["items"][0]["books_seen"] == 10
    assert http.get("/api/v1/admin/scan-history?from_date=2026-01-03&to_date=2026-01-01").status_code == 400
    assert http.get("/api/v1/admin/scan-history?scan_status=BAD").status_code == 422
    assert http.get("/api/v1/admin/scan-history?limit=101").status_code == 422


def test_retry_sent_requires_confirmation_and_csrf(client) -> None:
    http, engine = client
    assert http.get("/api/v1/admin/arrivals").status_code == 401
    assert http.get("/api/v1/admin/arrivals/1").status_code == 401
    csrf = setup_and_login(http)
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, name="Books", bookorbit_library_id=1, monitored=True)
        library.webhooks.append(Webhook(name="Target", url_encrypted="encrypted"))
        session.add(library)
        session.commit()
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=1, title="Existing")],
            scan_complete=True,
        )
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[
                ObservedBook(bookorbit_book_id=1, title="Existing"),
                ObservedBook(
                    bookorbit_book_id=2,
                    title="New",
                    authors=["Jane Author"],
                    metadata={"language": "de", "genres": ["Fantasy"], "files": [{"format": "epub", "absolutePath": "/private/test.epub"}]},
                ),
            ],
            scan_complete=True,
        )
        session.commit()
        event = session.scalar(select(Event))
        assert event is not None
        event.metadata_attempt_count = 2
        event.metadata_last_error = "private source error and credential"
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None
        item.status = QueueStatus.SENT
        item.next_retry_at = datetime(2026, 11, 27, 12, tzinfo=UTC)
        session.commit()
        item_id = item.id
        server_id = server.id
        library_id = library.id
    arrivals = http.get(f"/api/v1/admin/arrivals?server_id={server_id}&library_id={library_id}").json()
    library_summary = http.get("/api/v1/admin/libraries").json()[0]
    assert library_summary["book_count"] == 2 and library_summary["arrival_count"] == 1 and library_summary["last_scan"] is not None
    assert len(arrivals) == 1 and arrivals[0]["title"] == "New" and arrivals[0]["delivery_statuses"] == ["SENT"]
    detail = http.get(f"/api/v1/admin/arrivals/{arrivals[0]['event_id']}")
    assert detail.status_code == 200 and detail.json()["metadata"]["formats"] == ["epub"]
    assert detail.json()["deliveries"][0]["status"] == "SENT"
    assert detail.json()["deliveries"][0]["next_retry_at"].startswith("2026-11-27T12:00:00")
    processing = detail.json()["metadata_processing"]
    assert processing["attempt_count"] == 2 and processing["last_attempt_failed"] is True
    assert processing["not_before_at"] is not None and processing["deadline_at"] is not None
    assert "private source error and credential" not in detail.text
    assert "/private/" not in detail.text and "encrypted" not in detail.text
    assert http.get("/api/v1/admin/arrivals/999").status_code == 404
    assert "encrypted" not in str(arrivals)
    assert http.get("/api/v1/admin/arrivals?server_id=999").json() == []
    assert http.get("/api/v1/admin/arrivals?limit=101").status_code == 422
    assert (
        len(http.get("/api/v1/admin/arrivals?author=author&genre=fantasy&media_format=EPUB&language=DE&delivery_status=SENT").json()) == 1
    )
    assert http.get("/api/v1/admin/arrivals?author=missing").json() == []
    assert http.get("/api/v1/admin/arrivals?genre=missing").json() == []
    assert http.get("/api/v1/admin/arrivals?media_format=mp3").json() == []
    assert http.get("/api/v1/admin/arrivals?delivery_status=FAILED").json() == []
    detected_day = arrivals[0]["detected_at"].split("T")[0]
    assert len(http.get(f"/api/v1/admin/arrivals?detected_from={detected_day}&detected_to={detected_day}").json()) == 1
    assert http.get("/api/v1/admin/arrivals?detected_from=2026-12-31&detected_to=2026-01-01").status_code == 400
    path = f"/api/v1/admin/notifications/{item_id}/retry"
    listing = http.get("/api/v1/admin/notifications")
    assert listing.status_code == 200 and listing.json()[0]["book_title"] == "New"
    assert listing.json()[0]["next_retry_at"].startswith("2026-11-27T12:00:00")
    assert listing.json()[0]["sending_started_at"] is None
    assert len(http.get("/api/v1/admin/notifications?delivery_status=SENT").json()) == 1
    assert http.get("/api/v1/admin/notifications?delivery_status=FAILED").json() == []
    assert http.get("/api/v1/admin/notifications?offset=1").json() == []
    assert http.get("/api/v1/admin/notifications?delivery_status=UNKNOWN").status_code == 422
    assert "encrypted" not in listing.text
    assert http.get("/api/v1/admin/notifications?limit=101").status_code == 422
    assert http.post(path, headers={"origin": ORIGIN}, json={"confirm_sent_resend": True}).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.post(path, headers=headers, json={}).status_code == 400
    assert http.post(path, headers=headers, json={"confirm_sent_resend": "true"}).status_code == 422
    assert http.post(path, headers=headers, json={"confirm_sent_resend": True}).status_code == 200
    assert http.get(f"/api/v1/admin/notifications/{item_id}/history").status_code == 200
    detail = http.get(f"/api/v1/admin/arrivals/{arrivals[0]['event_id']}").json()
    assert detail["deliveries"][0]["attempts"][0]["error"] == "Manual retry requested"


def test_admin_disabled_and_invalid_origin_fail_closed(monkeypatch: pytest.MonkeyPatch, client) -> None:
    http, _engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ORIGIN", "http://notifier.example")
    get_settings.cache_clear()
    assert http.post("/api/v1/admin/login", headers={"origin": "http://notifier.example"}, json={"password": PASSWORD}).status_code == 503
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    assert http.get("/admin").status_code == 404
    assert http.get("/api/v1/admin/notifications/summary").status_code == 404


def test_sender_profiles_require_session_origin_and_csrf(client) -> None:
    http, _engine = client
    path = "/api/v1/admin/sender-profiles/global"
    payload = {"username": {"choice": "custom", "value": "My library"}, "avatar_url": {"choice": "original"}}
    assert http.get(path).status_code == 401
    csrf = setup_and_login(http)
    assert http.get(path).json()["username"]["value"] == "BookOrbit Notifier"
    assert http.put(path, headers={"origin": ORIGIN}, json=payload).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.put(path, headers=headers, json=payload).status_code == 200
    assert http.get(path).json()["username"]["value"] == "My library"
    payload["avatar_url"] = {"choice": "custom", "value": "https://127.0.0.1/image.png"}
    assert http.put(path, headers=headers, json=payload).status_code == 400
    assert http.get(path).json()["avatar_url"]["choice"] == "original"
    preview = {"scope": "global", "username": {"choice": "custom", "value": "Preview only"}, "avatar_url": {"choice": "inherit"}}
    assert http.post("/api/v1/admin/sender-profile-preview", headers={"origin": ORIGIN}, json=preview).status_code == 401
    assert http.post("/api/v1/admin/sender-profile-preview", headers=headers, json=preview).json() == {
        "username": "Preview only",
        "avatar_url": None,
        "avatar_is_bundled": False,
    }
    preview["avatar_url"] = {"choice": "logo"}
    result = http.post("/api/v1/admin/sender-profile-preview", headers=headers, json=preview).json()
    assert result == {"username": "Preview only", "avatar_url": BUNDLED_LOGO_URL, "avatar_is_bundled": True}
    logo = http.get("/admin-assets/notifier-logo.png")
    assert logo.status_code == 200 and logo.content.startswith(b"\x89PNG\r\n\x1a\n")
    payload = {"username": {"choice": "logo"}, "avatar_url": {"choice": "inherit"}}
    assert http.put(path, headers=headers, json=payload).status_code == 400
    assert http.get(path).json()["username"]["value"] == "My library"
    assert http.get(path).json()["username"]["value"] == "My library"
    assert http.get("/api/v1/admin/sender-profiles/library?scope_id=999").status_code == 400


def test_profile_scope_list_is_authenticated_and_redacted(client) -> None:
    http, engine = client
    assert http.get("/api/v1/admin/profile-scopes").status_code == 401
    with Session(engine) as session:
        server = Server(name="Example server", base_url="https://private.example", api_key_encrypted="secret-api-key")
        library = Library(server=server, name="Books", bookorbit_library_id=42)
        session.add_all([library, Webhook(name="New books", url_encrypted="secret-webhook")])
        session.commit()
    csrf = setup_and_login(http)
    result = http.get("/api/v1/admin/profile-scopes")
    assert result.status_code == 200
    assert result.json()["libraries"] == [{"id": 1, "name": "Books", "server_name": "Example server"}]
    assert result.json()["webhooks"] == [{"id": 1, "name": "New books", "server_name": None}]
    assert "secret" not in result.text and "private.example" not in result.text
    profile = {"username": {"choice": "custom", "value": "Books"}, "avatar_url": {"choice": "inherit"}}
    assert http.put("/api/v1/admin/sender-profiles/library?scope_id=1", headers={"origin": ORIGIN}, json=profile).status_code == 401
    assert (
        http.put(
            "/api/v1/admin/sender-profiles/library?scope_id=1", headers={"origin": ORIGIN, "x-csrf-token": csrf}, json=profile
        ).status_code
        == 200
    )
    assert http.get("/api/v1/admin/sender-profiles/library?scope_id=1").json()["username"]["value"] == "Books"


def test_preview_renders_verified_variables_and_requires_csrf(client) -> None:
    http, _engine = client
    payload = {
        "title": "{{title}} ({{published_year}})",
        "description": "{{narrators}} / {{page_count}} / {{duration}} / {{duration_seconds}}",
    }
    assert http.get("/api/v1/admin/template-variables").status_code == 401
    csrf = setup_and_login(http)
    variables = http.get("/api/v1/admin/template-variables").json()
    assert {"published_year", "narrators", "page_count", "duration_seconds"}.issubset(variables)
    assert http.post("/api/v1/admin/template-preview", headers={"origin": ORIGIN}, json=payload).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    result = http.post("/api/v1/admin/template-preview", headers=headers, json=payload)
    assert result.status_code == 200
    assert result.json()["title"] == "The Example Book (2024)"
    assert result.json()["description"] == "Sam Example / 320 / 08:00 h / 28800"
    series_preview = {
        "title": "{{series_tag}}",
        "description": "",
        "series_numbered_template": "Part {{series_index}} of {{series}}",
        "series_unnumbered_template": "Reihe: {{series}}",
    }
    assert http.post("/api/v1/admin/template-preview", headers=headers, json=series_preview).json()["title"] == "Part 2 of Example series"
    assert (
        http.post("/api/v1/admin/template-preview", headers=headers, json={**series_preview, "sample_series": "unnumbered"}).json()["title"]
        == "Reihe: Example series"
    )
    assert (
        http.post("/api/v1/admin/template-preview", headers=headers, json={**series_preview, "sample_series": "none"}).json()["title"] == ""
    )
    assert (
        http.post(
            "/api/v1/admin/template-preview", headers=headers, json={**series_preview, "series_unnumbered_template": "{{title}}"}
        ).status_code
        == 400
    )
    styled = {**payload, "color": 0x123456, "metadata_fields": ["narrators", "isbn13", "page_count"]}
    rendered = http.post("/api/v1/admin/template-preview", headers=headers, json=styled)
    assert rendered.status_code == 200 and rendered.json()["color"] == 0x123456
    assert [field["name"] for field in rendered.json()["fields"]] == ["Narrators", "Isbn13", "Page Count"]
    assert (
        http.post("/api/v1/admin/template-preview", headers=headers, json={**styled, "metadata_fields": ["isbn13", "isbn13"]}).status_code
        == 400
    )
    assert (
        http.post("/api/v1/admin/template-preview", headers=headers, json={"title": "{{not_allowed}}", "description": ""}).status_code
        == 400
    )


def test_server_connection_settings_are_validated_and_backward_compatible(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, _engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    csrf = setup_and_login(http)
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    create = {
        "name": "Source",
        "base_url": "https://books.example",
        "api_key": "key-secret",
        "public_url": "https://public.example/",
        "timeout_seconds": 30,
        "verify_ssl": False,
    }
    result = http.post("/api/v1/admin/servers", headers=headers, json=create)
    assert result.status_code == 201 and "key-secret" not in result.text
    server_id = result.json()["id"]
    server = http.get("/api/v1/admin/servers").json()[0]
    assert (server["public_url"], server["timeout_seconds"], server["verify_ssl"]) == ("https://public.example", 30, False)
    update = {"name": "Source", "scan_interval_seconds": 60}
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers=headers, json=update).status_code == 200
    server = http.get("/api/v1/admin/servers").json()[0]
    assert (server["public_url"], server["timeout_seconds"], server["verify_ssl"]) == ("https://public.example", 30, False)
    update.update({"public_url": None, "timeout_seconds": 20, "verify_ssl": True})
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers=headers, json=update).status_code == 200
    server = http.get("/api/v1/admin/servers").json()[0]
    assert (server["public_url"], server["timeout_seconds"], server["verify_ssl"]) == (None, 20, True)
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers={"origin": ORIGIN}, json=update).status_code == 401
    assert (
        http.put(
            f"/api/v1/admin/servers/{server_id}", headers=headers, json={**update, "public_url": "https://user:password@example.com"}
        ).status_code
        == 400
    )
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers=headers, json={**update, "timeout_seconds": 0}).status_code == 422
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers=headers, json={**update, "verify_ssl": "false"}).status_code == 422
    assert "key-secret" not in http.get("/api/v1/admin/servers").text


def test_library_sample_probe_is_read_only_scoped_and_redacted(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    csrf = setup_and_login(http)
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, name="Books", bookorbit_library_id=17)
        session.add_all([server, library])
        session.commit()
        server_id, library_id = server.id, library.id
    state = {"empty": False, "cover": True, "failure": False, "calls": []}

    class SampleClient:
        async def query_library_books(self, source_id, *, page, size):
            state["calls"].append(("query", source_id, page, size))
            if state["failure"]:
                raise BookOrbitApiError("private fixture error", 401)
            return SimpleNamespace(items=[] if state["empty"] else [SimpleNamespace(id=123)])

        async def get_book(self, book_id):
            state["calls"].append(("detail", book_id))
            return SimpleNamespace(title="private title")

        async def get_cover(self, book_id):
            state["calls"].append(("cover", book_id))
            return CoverImage(content=b"image", content_type="image/png", filename="cover.png") if state["cover"] else None

    @asynccontextmanager
    async def fake_connect(_self, selected_server_id):
        assert selected_server_id == server_id
        yield SampleClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", fake_connect)
    path = f"/api/v1/admin/servers/{server_id}/libraries/{library_id}/probe"
    assert http.post(path, headers={"origin": ORIGIN}).status_code == 401
    assert http.post(f"/api/v1/admin/servers/{server_id + 1}/libraries/{library_id}/probe", headers=headers).status_code == 404
    response = http.post(path, headers=headers)
    assert response.json() == {"metadata": "available", "cover": "available"}
    assert state["calls"] == [("query", 17, 0, 1), ("detail", 123), ("cover", 123)]
    assert "private title" not in response.text and "123" not in response.text
    state["cover"] = False
    assert http.post(path, headers=headers).json() == {"metadata": "available", "cover": "missing"}
    state["empty"] = True
    assert http.post(path, headers=headers).json() == {"metadata": "no_sample", "cover": "not_checked"}
    state.update(empty=False, failure=True)
    failure = http.post(path, headers=headers)
    assert failure.status_code == 502 and "private fixture error" not in failure.text


def test_server_webhook_and_library_management_is_redacted_and_csrf_protected(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    payload = {"name": "Books", "base_url": "https://books.example", "api_key": "bok_fixture_secret"}
    assert http.post("/api/v1/admin/servers", json=payload).status_code == 403
    csrf = setup_and_login(http)
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.post("/api/v1/admin/servers", headers={"origin": ORIGIN}, json=payload).status_code == 401
    response = http.post("/api/v1/admin/servers", headers=headers, json=payload)
    assert response.status_code == 201 and "bok_fixture_secret" not in response.text
    server_id = response.json()["id"]
    assert http.post(f"/api/v1/admin/servers/{server_id}/scan", headers=headers).status_code == 503
    update = {"name": "Renamed", "scan_interval_seconds": 120, "api_key": None}
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers={"origin": ORIGIN}, json=update).status_code == 401
    assert http.put(f"/api/v1/admin/servers/{server_id}", headers=headers, json=update).status_code == 200
    webhook_payload = {"name": "New", "webhook_url": "https://discord.com/api/webhooks/123/fixture-token"}
    response = http.post("/api/v1/admin/webhooks", headers=headers, json=webhook_payload)
    assert response.status_code == 201 and "fixture-token" not in response.text
    webhook_id = response.json()["id"]
    rotated = {"name": "New", "enabled": True, "webhook_url": "https://discord.com/api/webhooks/456/rotated-token"}
    assert http.put(f"/api/v1/admin/webhooks/{webhook_id}", headers=headers, json=rotated).status_code == 400
    with Session(engine) as session:
        from app.core.crypto import SecretCipher

        cipher = SecretCipher(get_settings().encryption_key.get_secret_value())
        assert cipher.decrypt(session.get(Webhook, webhook_id).url_encrypted).endswith("fixture-token")
        assert cipher.decrypt(session.get(Server, server_id).api_key_encrypted) == "bok_fixture_secret"
    rotated["confirm_destination_change"] = True
    assert http.put(f"/api/v1/admin/webhooks/{webhook_id}", headers=headers, json=rotated).status_code == 200
    assert "bok_fixture_secret" not in http.get("/api/v1/admin/servers").text
    assert "fixture-token" not in http.get("/api/v1/admin/webhooks").text

    async def fake_original(_self):
        return DiscordWebhookOriginal(username="Original name", avatar_url="https://cdn.discordapp.com/avatars/123/a.png")

    monkeypatch.setattr("app.api.admin.DiscordWebhookClient.get_original_profile", fake_original)
    original_path = f"/api/v1/admin/webhooks/{webhook_id}/original-profile"
    assert http.post(original_path, headers={"origin": ORIGIN}).status_code == 401
    original = http.post(original_path, headers=headers)
    assert original.status_code == 200 and original.json()["username"] == "Original name"
    assert "fixture-token" not in original.text and "rotated-token" not in original.text
    with Session(engine) as session:
        assert session.get(Server, server_id).api_key_encrypted != "bok_fixture_secret"
        assert "fixture-token" not in session.get(Webhook, webhook_id).url_encrypted

    class FakeClient:
        async def get_identity(self):
            return BookOrbitIdentity(authenticationMethod="api_key", username="should-not-leak")

        async def list_libraries(self):
            return [BookOrbitLibrary(id=12, name="Books")]

    @asynccontextmanager
    async def fake_connect(_self, _server_id):
        yield FakeClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", fake_connect)
    probe = http.post(f"/api/v1/admin/servers/{server_id}/test", headers=headers)
    assert probe.json() == {"status": "ok", "authentication_method": "api_key", "library_count": 1}
    assert "should-not-leak" not in probe.text and "bok_fixture_secret" not in probe.text
    assert http.get("/api/v1/admin/libraries").json() == []

    class FailingClient:
        async def get_identity(self):
            raise BookOrbitApiError("identity", 401)

    @asynccontextmanager
    async def failing_connect(_self, _server_id):
        yield FailingClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", failing_connect)
    failed_probe = http.post(f"/api/v1/admin/servers/{server_id}/test", headers=headers)
    assert failed_probe.status_code == 502 and "bok_fixture_secret" not in failed_probe.text
    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", fake_connect)
    assert http.post(f"/api/v1/admin/servers/{server_id}/sync-libraries", headers=headers).json() == {"created": 1, "updated": 0}
    library = http.get("/api/v1/admin/libraries").json()[0]
    assert library["monitored"] is False
    assert library["book_count"] == 0 and library["arrival_count"] == 0 and library["last_scan"] is None
    routing = {"monitored": True, "webhook_ids": [webhook_id], "template_id": None}
    assert http.put(f"/api/v1/admin/libraries/{library['id']}/routing", headers=headers, json=routing).status_code == 200
    assert http.get("/api/v1/admin/libraries").json()[0]["webhook_ids"] == [webhook_id]
    profile = {"username": {"choice": "custom", "value": "Library Bot"}, "avatar_url": {"choice": "original"}}
    assert http.put(f"/api/v1/admin/sender-profiles/library?scope_id={library['id']}", headers=headers, json=profile).status_code == 200
    captured = []

    async def fake_send(_self, target, notification):
        captured.append((target.username, target.avatar_url, notification.embed, notification.cover))
        return "message-id", 200

    monkeypatch.setattr("app.api.admin.DiscordNotificationSender.send", fake_send)
    test_path = f"/api/v1/admin/webhooks/{webhook_id}/test"
    assert http.post(test_path, headers={"origin": ORIGIN}, json={"library_id": library["id"]}).status_code == 401
    result = http.post(test_path, headers=headers, json={"library_id": library["id"]})
    assert result.status_code == 200 and "fixture-token" not in result.text
    assert captured[0][0] == "Library Bot" and captured[0][1] is None
    assert http.post(test_path, headers=headers, json={"library_id": 999}).status_code == 400
    draft = {
        "scope": "library",
        "scope_id": library["id"],
        "library_id": library["id"],
        "webhook_id": webhook_id,
        "username": {"choice": "custom", "value": "Draft Bot"},
        "avatar_url": {"choice": "original"},
    }
    preview = {
        "title": "{{title}} ({{published_year}})",
        "description": "{{narrators}}",
        "color": 0x123456,
        "metadata_fields": ["isbn13"],
        "show_cover": True,
    }
    assert (
        http.post(test_path, headers=headers, json={"library_id": library["id"], "preview": preview, "sender_profile": draft}).status_code
        == 200
    )
    assert captured[1][0] == "Draft Bot" and captured[1][2]["title"] == "The Example Book (2024)"
    assert captured[1][2]["description"] == "Sam Example"
    assert captured[1][2]["fields"][0]["name"] == "Isbn13" and captured[1][2]["color"] == 0x123456
    assert captured[1][2]["footer"]["text"] == "TEST"
    assert captured[0][3] is None
    assert captured[1][3].content_type == "image/png" and captured[1][3].content.startswith(b"\x89PNG\r\n\x1a\n")
    assert captured[1][3].content == http.get("/admin-assets/sample-cover.png").content
    assert http.get(f"/api/v1/admin/sender-profiles/library?scope_id={library['id']}").json()["username"]["value"] == "Library Bot"
    mismatched = {**draft, "webhook_id": webhook_id + 1}
    assert http.post(test_path, headers=headers, json={"library_id": library["id"], "sender_profile": mismatched}).status_code == 400
    assert (
        http.post(
            test_path, headers=headers, json={"library_id": library["id"], "preview": {"title": "{{invalid}}", "description": ""}}
        ).status_code
        == 400
    )
    assert http.post(test_path, headers=headers, json={"preview": {"title": "a" * 257, "description": ""}}).status_code == 200
    assert len(captured[2][2]["title"]) == 256 and captured[2][2]["title"].endswith("…")
    assert len(captured) == 3
    assert http.post(test_path, headers=headers, json={"preview": {**preview, "show_cover": False}}).status_code == 200
    assert captured[-1][3] is None

    async def fake_failure(_self, _target, _notification):
        raise DiscordDeliveryError(429)

    monkeypatch.setattr("app.api.admin.DiscordNotificationSender.send", fake_failure)
    failure = http.post(test_path, headers=headers, json={"library_id": library["id"]})
    assert failure.status_code == 502 and "fixture-token" not in failure.text
    delivery_path = f"/api/v1/admin/libraries/{library['id']}/delivery"
    delivery = {"delivery_mode": "DAILY_SUMMARY", "batch_window_seconds": 300, "daily_summary_time": "18:00", "timezone": "Europe/Berlin"}
    assert http.put(delivery_path, headers={"origin": ORIGIN}, json=delivery).status_code == 401
    assert http.put(delivery_path, headers=headers, json=delivery).status_code == 200
    assert http.get("/api/v1/admin/libraries").json()[0]["delivery_mode"] == "DAILY_SUMMARY"
    delivery["timezone"] = "Invalid/Zone"
    assert http.put(delivery_path, headers=headers, json=delivery).status_code == 400
    assert http.get("/api/v1/admin/libraries").json()[0]["timezone"] == "Europe/Berlin"
    payload["name"] = "Renamed"
    assert http.post("/api/v1/admin/servers", headers=headers, json=payload).status_code == 409
    assert http.put(f"/api/v1/admin/servers/{server_id}/enabled", headers=headers, json={"enabled": False}).status_code == 200


def test_template_create_update_and_validation(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, _engine = client
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    payload = {"name": "New books", "title_template": "{{title}}", "description_template": "{{narrators}} · {{published_year}}"}
    assert http.get("/api/v1/admin/templates").status_code == 401
    csrf = setup_and_login(http)
    assert http.post("/api/v1/admin/templates", headers={"origin": ORIGIN}, json=payload).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    result = http.post("/api/v1/admin/templates", headers=headers, json=payload)
    assert result.status_code == 201
    template_id = result.json()["id"]
    assert http.get("/api/v1/admin/templates").json()[0]["description_template"] == payload["description_template"]
    payload["title_template"] = "{% import os %}"
    assert http.put(f"/api/v1/admin/templates/{template_id}", headers=headers, json=payload).status_code == 400
    assert http.get("/api/v1/admin/templates").json()[0]["title_template"] == "{{title}}"
    payload["title_template"] = "New: {{title}}"
    payload["metadata_fields"] = ["isbn13", "narrators"]
    payload["series_numbered_template"] = "Part {{series_index}} of {{series}}"
    payload["series_unnumbered_template"] = "Series: {{series}}"
    assert http.put(f"/api/v1/admin/templates/{template_id}", headers=headers, json=payload).status_code == 200
    assert http.get("/api/v1/admin/templates").json()[0]["title_template"] == "New: {{title}}"
    assert http.get("/api/v1/admin/templates").json()[0]["metadata_fields"] == ["isbn13", "narrators"]
    stored = http.get("/api/v1/admin/templates").json()[0]
    assert stored["series_numbered_template"] == "Part {{series_index}} of {{series}}"
    assert stored["series_unnumbered_template"] == "Series: {{series}}"
    payload["series_numbered_template"] = "{{series_tag}}"
    assert http.put(f"/api/v1/admin/templates/{template_id}", headers=headers, json=payload).status_code == 400
    assert http.get("/api/v1/admin/templates").json()[0]["series_numbered_template"] == stored["series_numbered_template"]


def test_manual_scan_requires_csrf_and_reports_failure_without_secrets(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, _engine = client
    csrf = setup_and_login(http)
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_RUNTIME_ENABLED", "true")
    get_settings.cache_clear()

    class FakeScheduler:
        async def run_manual_scan(self, server_id):
            return SimpleNamespace(server_id=server_id, error=None, scan=None, metadata=None)

    monkeypatch.setitem(app.state._state, "runtime_scheduler", FakeScheduler())
    assert http.post("/api/v1/admin/servers/7/scan", headers={"origin": ORIGIN}).status_code == 401
    result = http.post("/api/v1/admin/servers/7/scan", headers={"origin": ORIGIN, "x-csrf-token": csrf})
    assert result.status_code == 200 and result.json()["server_id"] == 7

    class FailingScheduler:
        async def run_manual_scan(self, server_id):
            return SimpleNamespace(server_id=server_id, error="fixture-sensitive-details", scan=None, metadata=None)

    monkeypatch.setitem(app.state._state, "runtime_scheduler", FailingScheduler())
    result = http.post("/api/v1/admin/servers/7/scan", headers={"origin": ORIGIN, "x-csrf-token": csrf})
    assert result.status_code == 502 and "fixture-sensitive-details" not in result.text


def test_password_change_requires_csrf_and_current_password(client) -> None:
    http, _engine = client
    csrf = setup_and_login(http)
    path = "/api/v1/admin/change-password"
    payload = {"current_password": PASSWORD, "new_password": "new local password for testing"}
    assert http.post(path, headers={"origin": ORIGIN}, json=payload).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.post(path, headers=headers, json={**payload, "current_password": "incorrect password"}).status_code == 401
    assert http.post(path, headers=headers, json=payload).status_code == 200
    assert http.get("/api/v1/admin/notifications/summary").status_code == 401
    assert http.post("/api/v1/admin/login", headers={"origin": ORIGIN}, json={"password": PASSWORD}).status_code == 401
    assert http.post("/api/v1/admin/login", headers={"origin": ORIGIN}, json={"password": payload["new_password"]}).status_code == 200


def test_arrival_cover_uses_protected_source_without_exposing_credentials(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, engine = client
    assert http.get("/api/v1/admin/arrivals/1/cover").status_code == 401
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    setup_and_login(http)
    with Session(engine) as session:
        source = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=source, name="Books", bookorbit_library_id=1)
        book = Book(server=source, library=library, bookorbit_book_id=17, title="Test")
        session.add(book)
        session.flush()
        event = Event(server_id=source.id, library_id=library.id, book_id=book.id, event_type=EventType.BOOK_ADDED)
        session.add(event)
        session.commit()
        event_id = event.id

    class FakeClient:
        async def get_cover(self, book_id):
            assert book_id == 17
            return CoverImage(content=b"fake-image", content_type="image/png", filename="cover.png")

    @asynccontextmanager
    async def fake_connect(_self, _server_id):
        yield FakeClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", fake_connect)
    response = http.get(f"/api/v1/admin/arrivals/{event_id}/cover")
    assert response.status_code == 200 and response.content == b"fake-image"
    assert response.headers["content-type"] == "image/png" and response.headers["cache-control"] == "private, no-store"
    assert "books.example" not in str(response.headers) and "encrypted" not in str(response.headers)
    assert http.get("/api/v1/admin/arrivals/999/cover").status_code == 404

    class UnsafeClient:
        async def get_cover(self, _book_id):
            return CoverImage(content=b"<svg/>", content_type="image/svg+xml", filename="cover.svg")

    @asynccontextmanager
    async def unsafe_connect(_self, _server_id):
        yield UnsafeClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", unsafe_connect)
    assert http.get(f"/api/v1/admin/arrivals/{event_id}/cover").status_code == 502
