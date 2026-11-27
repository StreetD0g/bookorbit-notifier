"""Sender field precedence and Discord transport contracts."""

import json

import httpx
import pytest

from app.providers.notifications.discord.client import DiscordWebhookClient
from app.providers.notifications.discord.sender_profile import BUNDLED_LOGO_URL, ProfileChoice, ProfileField, SenderProfile, resolve_profile
from app.schemas.bookorbit import CoverImage


def test_independent_precedence_and_explicit_original() -> None:
    custom = ProfileChoice.CUSTOM
    library = SenderProfile(username=ProfileField(custom, "Library"))
    webhook = SenderProfile(username=ProfileField(custom, "Webhook"), avatar_url=ProfileField(custom, "https://example.com/a.png"))
    assert resolve_profile(library, webhook) == ("Library", "https://example.com/a.png")
    assert resolve_profile(SenderProfile(username=ProfileField(ProfileChoice.ORIGINAL)), webhook) == (None, "https://example.com/a.png")
    assert resolve_profile() == ("BookOrbit Notifier", None)
    with pytest.raises(ValueError):
        ProfileField(custom, " ")


def test_bundled_logo_obeys_independent_avatar_precedence() -> None:
    global_profile = SenderProfile(avatar_url=ProfileField(ProfileChoice.LOGO))
    webhook = SenderProfile(username=ProfileField(ProfileChoice.CUSTOM, "Webhook"))
    assert resolve_profile(webhook=webhook, global_profile=global_profile) == ("Webhook", BUNDLED_LOGO_URL)
    original = SenderProfile(avatar_url=ProfileField(ProfileChoice.ORIGINAL))
    assert resolve_profile(library=original, webhook=webhook, global_profile=global_profile) == ("Webhook", None)
    replacement = SenderProfile(avatar_url=ProfileField(ProfileChoice.CUSTOM, "https://example.com/custom.png"))
    assert resolve_profile(library=replacement, webhook=webhook, global_profile=global_profile) == (
        "Webhook",
        "https://example.com/custom.png",
    )
    with pytest.raises(ValueError, match="only valid for avatars"):
        resolve_profile(library=SenderProfile(username=ProfileField(ProfileChoice.LOGO)))


@pytest.mark.asyncio
async def test_sender_overrides_are_per_message_for_json_and_attachment() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "1"})

    client = DiscordWebhookClient("https://discord.example/webhook", transport=httpx.MockTransport(handler))
    try:
        await client.send_embed({"title": "One"}, username="First", avatar_url="https://example.com/a.png")
        await client.send_embed(
            {"title": "Two"}, cover=CoverImage(content=b"image", content_type="image/jpeg", filename="cover.jpg"), username="Second"
        )
        await client.send_embed({"title": "Three"}, username="Third", avatar_url=BUNDLED_LOGO_URL)
    finally:
        await client.aclose()
    assert json.loads(requests[0].content)["username"] == "First"
    assert json.loads(requests[0].content)["avatar_url"] == "https://example.com/a.png"
    assert b'"username": "Second"' in requests[1].content
    assert b'"avatar_url"' not in requests[1].content
    assert json.loads(requests[2].content)["avatar_url"] == BUNDLED_LOGO_URL
    assert all(request.method == "POST" for request in requests)
