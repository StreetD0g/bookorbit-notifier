import json

import httpx
import pytest

from app.providers.notifications.discord.client import DiscordDeliveryError, DiscordWebhookClient
from app.schemas.bookorbit import CoverImage


@pytest.mark.asyncio
async def test_sends_cover_as_discord_attachment() -> None:
    """The embed points at Discord's attachment, not at BookOrbit's protected URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["wait"] == "true"
        assert b'attachment://cover-1.jpg' in request.content
        assert b"image-bytes" in request.content
        return httpx.Response(200, json={"id": "discord-message-1"})

    client = DiscordWebhookClient("https://discord.example/webhook", transport=httpx.MockTransport(handler))
    try:
        message_id, status_code = await client.send_embed(
            {"title": "New book"},
            cover=CoverImage(content=b"image-bytes", content_type="image/jpeg", filename="cover-1.jpg"),
        )
    finally:
        await client.aclose()

    assert message_id == "discord-message-1"
    assert status_code == 200


@pytest.mark.asyncio
async def test_captures_discord_rate_limit_hint() -> None:
    """The future persistent queue can schedule retry work from Discord's hint."""

    client = DiscordWebhookClient(
        "https://discord.example/webhook",
        transport=httpx.MockTransport(lambda _: httpx.Response(429, json={"retry_after": 2.5})),
    )
    try:
        with pytest.raises(DiscordDeliveryError) as error:
            await client.send_embed({"title": "New book"})
    finally:
        await client.aclose()

    assert error.value.status_code == 429
    assert error.value.retry_after_seconds == 2.5


@pytest.mark.asyncio
async def test_sends_up_to_ten_embeds_in_one_discord_message() -> None:
    """Grouped delivery uses Discord's embeds array rather than multiple webhook posts."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"embeds": [{"title": "One"}, {"title": "Two"}]}
        return httpx.Response(200, json={"id": "discord-batch-1"})

    client = DiscordWebhookClient("https://discord.example/webhook", transport=httpx.MockTransport(handler))
    try:
        message_id, status_code = await client.send_embeds([{"title": "One"}, {"title": "Two"}])
    finally:
        await client.aclose()

    assert message_id == "discord-batch-1"
    assert status_code == 200
