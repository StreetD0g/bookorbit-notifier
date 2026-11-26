"""Persistence and worker integration for scoped Discord sender settings."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models import DeliveryMode, Library, Server, Webhook
from app.providers.notifications.discord.sender_profile import ProfileChoice, ProfileField, SenderProfile
from app.queue.state import DeliveryClaim
from app.queue.worker import DiscordDeliveryWorker, WebhookTarget
from app.services.sender_profiles import SenderProfileService


def test_profiles_persist_and_resolve_for_same_webhook(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'profiles.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        session.add_all(
            [
                Library(server=server, bookorbit_library_id=1, name="Books"),
                Library(server=server, bookorbit_library_id=2, name="Audio"),
                Webhook(name="Target", url_encrypted="encrypted"),
            ]
        )
    with factory() as session:
        libraries = session.scalars(select(Library).order_by(Library.id)).all()
        webhook = session.scalar(select(Webhook))
        assert webhook is not None
        first, second, webhook_id = libraries[0].id, libraries[1].id, webhook.id
    service = SenderProfileService(factory)
    service.configure("webhook", webhook_id, SenderProfile(avatar_url=ProfileField(ProfileChoice.CUSTOM, "https://example.com/avatar.png")))
    service.configure("library", first, SenderProfile(username=ProfileField(ProfileChoice.CUSTOM, "Books")))
    service.configure("library", second, SenderProfile(username=ProfileField(ProfileChoice.ORIGINAL)))
    assert service.resolve(first, webhook_id) == ("Books", "https://example.com/avatar.png")
    assert service.resolve(second, webhook_id) == (None, "https://example.com/avatar.png")
    preview = SenderProfile(username=ProfileField(ProfileChoice.ORIGINAL))
    assert service.preview("library", first, preview, library_id=first, webhook_id=webhook_id) == (None, "https://example.com/avatar.png")
    assert service.resolve(first, webhook_id)[0] == "Books"  # Preview must never persist its override.
    unsaved_global = SenderProfile(username=ProfileField(ProfileChoice.CUSTOM, "Global draft"))
    assert service.preview("global", None, unsaved_global, library_id=second, webhook_id=webhook_id) == (
        None,
        "https://example.com/avatar.png",
    )
    with pytest.raises(ValueError, match="does not match"):
        service.preview("library", first, preview, library_id=second, webhook_id=webhook_id)

    class Resolver:
        def resolve(self, target_id: int) -> WebhookTarget:
            return WebhookTarget(target_id, "https://discord.example/webhook")

    worker = DiscordDeliveryWorker(factory, Resolver(), None)  # type: ignore[arg-type]
    claim = DeliveryClaim(
        queue_item_id=1, event_id=1, webhook_id=webhook_id, library_id=first, delivery_mode=DeliveryMode.SINGLE, attempt_count=1
    )
    target = worker._target_for_claim(claim)
    assert (target.username, target.avatar_url) == service.resolve(first, webhook_id)
    engine.dispose()


@pytest.mark.parametrize("url", ["http://example.com/a", "https://127.0.0.1/a", "https://host.local/a", "https://user:pass@example.com/a"])
def test_rejects_non_public_avatar_urls(tmp_path: Path, url: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'profiles.db'}")
    Base.metadata.create_all(engine)
    service = SenderProfileService(sessionmaker(engine))
    with pytest.raises(ValueError):
        service.configure("global", None, SenderProfile(avatar_url=ProfileField(ProfileChoice.CUSTOM, url)))
    engine.dispose()
