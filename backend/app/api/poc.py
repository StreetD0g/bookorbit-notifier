"""Development-only diagnostics; disabled by default to avoid a credential relay."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.providers.events.bookorbit.client import BookOrbitApiError, bookorbit_client
from app.providers.notifications.discord.client import DiscordDeliveryError, DiscordWebhookClient
from app.schemas.poc import BookOrbitProbeRequest, BookOrbitProbeResponse, DiscordProbeRequest, DiscordProbeResponse
from app.services.poc import probe_bookorbit, send_discord_probe

router = APIRouter(prefix="/poc", tags=["proof-of-concept"])


def _ensure_enabled() -> None:
    """Refuse diagnostic credential submission unless an operator opted in."""

    if not get_settings().poc_endpoints_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("/bookorbit/test", response_model=BookOrbitProbeResponse)
async def test_bookorbit_connection(request: BookOrbitProbeRequest) -> BookOrbitProbeResponse:
    """Test authentication, libraries, book details, and optional cover access."""

    _ensure_enabled()
    try:
        async with bookorbit_client(request.base_url, request.api_key.get_secret_value()) as client:
            return await probe_bookorbit(client)
    except BookOrbitApiError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/discord/test", response_model=DiscordProbeResponse)
async def test_discord_webhook(request: DiscordProbeRequest) -> DiscordProbeResponse:
    """Send an explicit test message; no webhook URL is stored or returned."""

    _ensure_enabled()
    client = DiscordWebhookClient(request.webhook_url.get_secret_value())
    try:
        return await send_discord_probe(client)
    except DiscordDeliveryError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    finally:
        await client.aclose()
