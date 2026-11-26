"""Build short-lived read-only BookOrbit clients from encrypted server configuration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher
from app.database.models import Server
from app.providers.events.bookorbit.client import BookOrbitClient
from app.schemas.bookorbit import CoverImage

type SessionFactory = Callable[[], Session]


class EncryptedBookOrbitClientFactory:
    """Decrypt a server key only while a scanner owns an authenticated HTTP client."""

    def __init__(self, session_factory: SessionFactory, cipher: SecretCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    @asynccontextmanager
    async def connect(self, server_id: int) -> AsyncIterator[BookOrbitClient]:
        """Yield one configured client; credentials are not retained by the factory."""

        with self._session_factory() as session:
            server = session.get(Server, server_id)
            if server is None or not server.enabled:
                raise ValueError("Server is missing or disabled")
            base_url = server.base_url
            api_key = self._cipher.decrypt(server.api_key_encrypted)
            timeout_seconds = server.timeout_seconds
            verify_ssl = server.verify_ssl
        client = BookOrbitClient(base_url, api_key, timeout_seconds=timeout_seconds, verify_ssl=verify_ssl)
        try:
            yield client
        finally:
            await client.aclose()

    async def get_cover(self, server_id: int, book_id: int) -> CoverImage | None:
        """Fetch a cover through the same short-lived authenticated source client."""

        async with self.connect(server_id) as client:
            return await client.get_cover(book_id)
