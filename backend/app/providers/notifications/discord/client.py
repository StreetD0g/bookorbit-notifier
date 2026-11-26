"""Discord webhook transport with optional authenticated-source cover attachment."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.schemas.bookorbit import CoverImage


class DiscordDeliveryError(RuntimeError):
    """A delivery failed while retaining only actionable, non-secret state."""

    def __init__(self, status_code: int | None = None, retry_after_seconds: float | None = None) -> None:
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        message = "Discord webhook delivery failed"
        if status_code is not None:
            message = f"{message} (HTTP {status_code})"
        super().__init__(message)


class DiscordWebhookClient:
    """Send Discord embeds without exposing BookOrbit credentials to Discord."""

    def __init__(
        self,
        webhook_url: str,
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=False, transport=transport)

    async def aclose(self) -> None:
        """Release the transport connection pool."""

        await self._client.aclose()

    async def send_embed(self, embed: dict[str, Any], *, cover: CoverImage | None = None) -> tuple[str | None, int]:
        """Post one embed and optionally refer to an uploaded image attachment."""

        if cover is None:
            return await self.send_embeds([embed])
        payload = {"embeds": [embed]}
        payload["embeds"][0]["thumbnail"] = {"url": f"attachment://{cover.filename}"}
        request = self._client.build_request(
            "POST",
            self._webhook_url,
            params={"wait": "true"},
            data={"payload_json": json.dumps(payload)},
            files={"files[0]": (cover.filename, cover.content, cover.content_type)},
        )

        return await self._send_request(request)

    async def send_embeds(self, embeds: list[dict[str, Any]]) -> tuple[str | None, int]:
        """Send one Discord message containing one to ten embeds without source attachments."""

        if not 1 <= len(embeds) <= 10:
            raise ValueError("Discord messages must contain between one and ten embeds")
        request = self._client.build_request("POST", self._webhook_url, params={"wait": "true"}, json={"embeds": embeds})
        return await self._send_request(request)

    async def _send_request(self, request: httpx.Request) -> tuple[str | None, int]:
        """Send a prepared request and reduce Discord errors to safe retry context."""
        try:
            response = await self._client.send(request)
        except httpx.HTTPError as error:
            raise DiscordDeliveryError() from error
        if response.is_error:
            raise DiscordDeliveryError(response.status_code, self._retry_after(response))
        message_id: str | None = None
        if response.content:
            try:
                response_json = response.json()
                message_id_value = response_json.get("id") if isinstance(response_json, dict) else None
                message_id = str(message_id_value) if message_id_value is not None else None
            except (ValueError, UnicodeDecodeError):
                # Discord can legitimately answer without a JSON body; success is still success.
                pass
        return message_id, response.status_code

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Extract Discord's retry advice without depending on an error-body shape."""

        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                return None
        try:
            body = response.json()
            value = body.get("retry_after") if isinstance(body, dict) else None
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None
