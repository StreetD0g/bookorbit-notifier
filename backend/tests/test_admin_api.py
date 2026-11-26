"""Exercise the administrator surface through HTTP, including failure paths."""

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import Base
from app.database.models import Event, Library, NotificationQueueItem, QueueStatus, Server, Webhook
from app.database.session import create_database_engine
from app.main import app
from app.scanner.reconcile import ObservedBook, reconcile_library_inventory
from app.schemas.bookorbit import BookOrbitLibrary

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


def test_setup_login_cookie_csrf_and_logout(client) -> None:
    http, _engine = client
    assert http.get("/api/v1/admin/notifications/summary").status_code == 401
    assert http.get("/admin").status_code == 200
    assert "frame-ancestors 'none'" in http.get("/admin").headers["content-security-policy"]
    assert http.get("/admin-assets/admin.js").status_code == 200
    assert http.get("/admin-assets/admin.css").status_code == 200
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
    assert http.post("/api/v1/admin/logout", headers={"origin": ORIGIN}).status_code == 401
    assert http.post("/api/v1/admin/logout", headers={"origin": "https://evil.example", "x-csrf-token": csrf}).status_code == 403
    assert http.post("/api/v1/admin/logout", headers={"origin": ORIGIN, "x-csrf-token": csrf}).status_code == 200
    assert http.get("/api/v1/admin/notifications/summary").status_code == 401


def test_retry_sent_requires_confirmation_and_csrf(client) -> None:
    http, engine = client
    csrf = setup_and_login(http)
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        library = Library(server=server, name="Books", bookorbit_library_id=1, monitored=True)
        library.webhooks.append(Webhook(name="Target", url_encrypted="encrypted"))
        session.add(library)
        session.commit()
        reconcile_library_inventory(session, server_id=server.id, library_id=library.id, observed_books=[], scan_complete=True)
        reconcile_library_inventory(
            session,
            server_id=server.id,
            library_id=library.id,
            observed_books=[ObservedBook(bookorbit_book_id=2, title="New")],
            scan_complete=True,
        )
        session.commit()
        assert session.scalar(select(Event)) is not None
        item = session.scalar(select(NotificationQueueItem))
        assert item is not None
        item.status = QueueStatus.SENT
        session.commit()
        item_id = item.id
    path = f"/api/v1/admin/notifications/{item_id}/retry"
    listing = http.get("/api/v1/admin/notifications")
    assert listing.status_code == 200 and listing.json()[0]["book_title"] == "New"
    assert "encrypted" not in listing.text
    assert http.get("/api/v1/admin/notifications?limit=101").status_code == 422
    assert http.post(path, headers={"origin": ORIGIN}, json={"confirm_sent_resend": True}).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    assert http.post(path, headers=headers, json={}).status_code == 400
    assert http.post(path, headers=headers, json={"confirm_sent_resend": "true"}).status_code == 422
    assert http.post(path, headers=headers, json={"confirm_sent_resend": True}).status_code == 200
    assert http.get(f"/api/v1/admin/notifications/{item_id}/history").status_code == 200


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
    payload = {"title": "{{title}} ({{published_year}})", "description": "{{narrators}} / {{page_count}} / {{duration_seconds}}"}
    assert http.get("/api/v1/admin/template-variables").status_code == 401
    csrf = setup_and_login(http)
    variables = http.get("/api/v1/admin/template-variables").json()
    assert {"published_year", "narrators", "page_count", "duration_seconds"}.issubset(variables)
    assert http.post("/api/v1/admin/template-preview", headers={"origin": ORIGIN}, json=payload).status_code == 401
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    result = http.post("/api/v1/admin/template-preview", headers=headers, json=payload)
    assert result.status_code == 200
    assert result.json()["title"] == "The Example Book (2024)"
    assert result.json()["description"] == "Sam Example / 320 / 28800"
    assert (
        http.post("/api/v1/admin/template-preview", headers=headers, json={"title": "{{not_allowed}}", "description": ""}).status_code
        == 400
    )


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
    webhook_payload = {"name": "New", "webhook_url": "https://discord.com/api/webhooks/123/fixture-token"}
    response = http.post("/api/v1/admin/webhooks", headers=headers, json=webhook_payload)
    assert response.status_code == 201 and "fixture-token" not in response.text
    webhook_id = response.json()["id"]
    assert "bok_fixture_secret" not in http.get("/api/v1/admin/servers").text
    assert "fixture-token" not in http.get("/api/v1/admin/webhooks").text
    with Session(engine) as session:
        assert session.get(Server, server_id).api_key_encrypted != "bok_fixture_secret"
        assert "fixture-token" not in session.get(Webhook, webhook_id).url_encrypted

    class FakeClient:
        async def list_libraries(self):
            return [BookOrbitLibrary(id=12, name="Books")]

    @asynccontextmanager
    async def fake_connect(_self, _server_id):
        yield FakeClient()

    monkeypatch.setattr("app.api.admin.EncryptedBookOrbitClientFactory.connect", fake_connect)
    assert http.post(f"/api/v1/admin/servers/{server_id}/sync-libraries", headers=headers).json() == {"created": 1, "updated": 0}
    library = http.get("/api/v1/admin/libraries").json()[0]
    assert library["monitored"] is False
    routing = {"monitored": True, "webhook_ids": [webhook_id], "template_id": None}
    assert http.put(f"/api/v1/admin/libraries/{library['id']}/routing", headers=headers, json=routing).status_code == 200
    assert http.get("/api/v1/admin/libraries").json()[0]["webhook_ids"] == [webhook_id]
    assert http.post("/api/v1/admin/servers", headers=headers, json=payload).status_code == 409
    assert http.put(f"/api/v1/admin/servers/{server_id}/enabled", headers=headers, json={"enabled": False}).status_code == 200
