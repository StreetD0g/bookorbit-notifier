from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.crypto import SecretCipher
from app.database.base import Base
from app.database.models import DeliveryMode, Library, NotificationTemplate, Server, Webhook
from app.schemas.bookorbit import BookOrbitLibrary
from app.services.configuration import ConfigurationService, CreateServer, CreateTemplate, CreateWebhook


@pytest.fixture
def configuration_service(tmp_path: Path) -> tuple[ConfigurationService, sessionmaker[Session]]:
    """Create an isolated encrypted configuration service with no real credentials."""

    engine = create_engine(f"sqlite:///{tmp_path / 'configuration.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return ConfigurationService(factory, SecretCipher(Fernet.generate_key())), factory


def test_server_credentials_are_encrypted_and_views_are_redacted(
    configuration_service: tuple[ConfigurationService, sessionmaker[Session]],
) -> None:
    """Plaintext keys are neither stored directly nor included in administrator list views."""

    service, factory = configuration_service
    view = service.create_server(CreateServer(name="Main", base_url="https://books.example/", api_key="bok_secret"))

    assert view.base_url == "https://books.example"
    assert not hasattr(view, "api_key")
    with factory() as session:
        server = session.get(Server, view.id)
        assert server is not None
        assert server.api_key_encrypted != "bok_secret"
    assert service.list_servers() == [view]


def test_library_sync_routing_and_template_assignment(
    configuration_service: tuple[ConfigurationService, sessionmaker[Session]],
) -> None:
    """Multiple source libraries can independently route to the same encrypted webhook."""

    service, factory = configuration_service
    server = service.create_server(CreateServer(name="Main", base_url="https://books.example", api_key="bok_secret"))
    synced = service.synchronize_libraries(
        server.id,
        [BookOrbitLibrary(id=1, name="Books"), BookOrbitLibrary(id=2, name="Audio")],
    )
    webhook = service.create_webhook(CreateWebhook(name="New media", webhook_url="https://discord.com/api/webhooks/123/token"))
    template_id = service.create_template(CreateTemplate(name="Default", title_template="{{title}}", description_template="{{authors}}"))
    with factory() as session:
        library = session.scalar(select(Library).where(Library.bookorbit_library_id == 2))
        assert library is not None
        library_id = library.id

    service.configure_library_routing(library_id, monitored=True, webhook_ids=[webhook.id], template_id=template_id)

    assert synced.created == 2
    with factory() as session:
        library = session.get(Library, library_id)
        assert library is not None
        assert library.monitored is True
        assert [target.id for target in library.webhooks] == [webhook.id]
        assert library.template_id == template_id
        assert session.get(NotificationTemplate, template_id) is not None
        stored_webhook = session.get(Webhook, webhook.id)
        assert stored_webhook is not None and "discord.com" not in stored_webhook.url_encrypted


def test_configuration_rejects_unsafe_urls_and_executable_template_syntax(
    configuration_service: tuple[ConfigurationService, sessionmaker[Session]],
) -> None:
    """Configuration cannot turn templates into a code-execution surface or accept malformed destinations."""

    service, _factory = configuration_service
    with pytest.raises(ValueError, match="official Discord HTTPS host"):
        service.create_webhook(CreateWebhook(name="Unsafe", webhook_url="https://example.com/api/webhooks/123/token"))
    with pytest.raises(ValueError, match="unsupported template syntax"):
        service.create_template(CreateTemplate(name="Unsafe", title_template="{% import os %}"))
    with pytest.raises(ValueError, match="distinct"):
        service.create_template(CreateTemplate(name="Duplicates", metadata_fields=("isbn13", "isbn13")))


def test_library_delivery_configuration_validates_schedule_inputs(
    configuration_service: tuple[ConfigurationService, sessionmaker[Session]],
) -> None:
    """Aggregation settings persist only after their local timezone and time are valid."""

    service, factory = configuration_service
    server = service.create_server(CreateServer(name="Main", base_url="https://books.example", api_key="bok_secret"))
    service.synchronize_libraries(server.id, [BookOrbitLibrary(id=1, name="Books")])
    with factory() as session:
        library = session.scalar(select(Library))
        assert library is not None
        library_id = library.id

    service.configure_library_delivery(
        library_id,
        delivery_mode=DeliveryMode.DAILY_SUMMARY,
        batch_window_seconds=600,
        daily_summary_time="7:05",
        timezone="Europe/Berlin",
    )

    with factory() as session:
        library = session.get(Library, library_id)
        assert library is not None
        assert library.delivery_mode == DeliveryMode.DAILY_SUMMARY
        assert library.daily_summary_time == "07:05"
    with pytest.raises(ValueError, match="Timezone is not available"):
        service.configure_library_delivery(library_id, delivery_mode=DeliveryMode.SINGLE, timezone="Invalid/Zone")
