"""Minimal, read-only client for the BookOrbit routes verified in Phase 0."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from pydantic import AnyHttpUrl

from app.schemas.bookorbit import (
    BookOrbitBookCard,
    BookOrbitBookDetail,
    BookOrbitBookPage,
    BookOrbitIdentity,
    BookOrbitLibrary,
    CoverImage,
)


class BookOrbitApiError(RuntimeError):
    """A source request failed without retaining secret-bearing response content."""

    def __init__(self, operation: str, status_code: int | None = None) -> None:
        self.operation = operation
        self.status_code = status_code
        detail = f"BookOrbit {operation} request failed"
        if status_code is not None:
            detail = f"{detail} (HTTP {status_code})"
        super().__init__(detail)


class BookOrbitClient:
    """Own BookOrbit HTTP lifetime and expose only non-mutating operations.

    This class intentionally sends the API key in an HTTP header, never in a URL.
    Redirects are disabled so a credential-bearing request cannot silently move to
    a different origin.
    """

    def __init__(
        self,
        base_url: str | AnyHttpUrl,
        api_key: str,
        *,
        timeout_seconds: float = 15.0,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = str(base_url).rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1/",
            headers=self._headers,
            timeout=httpx.Timeout(timeout_seconds),
            verify=verify_ssl,
            follow_redirects=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Release the underlying connection pool."""

        await self._client.aclose()

    async def get_identity(self) -> BookOrbitIdentity:
        """Verify API-key authentication through the documented identity endpoint."""

        response = await self._request("GET", "auth/me", operation="identity")
        return BookOrbitIdentity.model_validate(response.json())

    async def list_libraries(self) -> list[BookOrbitLibrary]:
        """Return only libraries visible to the read-only source key."""

        response = await self._request("GET", "libraries", operation="library discovery")
        return [BookOrbitLibrary.model_validate(item) for item in response.json()]

    async def query_library_books(self, library_id: int, *, page: int = 0, size: int = 200) -> BookOrbitBookPage:
        """Fetch one verified, zero-based page in a library's inventory."""

        payload = {
            "sort": [{"field": "addedAt", "dir": "desc"}],
            "pagination": {"page": page, "size": size},
        }
        response = await self._request(
            "POST",
            f"libraries/{library_id}/books",
            operation="library book query",
            json=payload,
        )
        return BookOrbitBookPage.model_validate(response.json())

    async def iter_library_books(self, library_id: int, *, page_size: int = 200) -> AsyncIterator[BookOrbitBookCard]:
        """Page the complete inventory; IDs, not timestamps, establish novelty."""

        page_number = 0
        yielded = 0
        while True:
            result = await self.query_library_books(library_id, page=page_number, size=page_size)
            for book in result.items:
                yielded += 1
                yield book
            if yielded >= result.total or not result.items:
                return
            page_number += 1

    async def get_book(self, book_id: int) -> BookOrbitBookDetail:
        """Refresh details for an accessible logical BookOrbit book."""

        response = await self._request("GET", f"books/{book_id}", operation="book detail")
        return BookOrbitBookDetail.model_validate(response.json())

    async def get_cover(self, book_id: int) -> CoverImage | None:
        """Download one authenticated cover, returning None when no cover is present."""

        try:
            response = await self._request("GET", f"books/{book_id}/cover", operation="cover download")
        except BookOrbitApiError as error:
            if error.status_code == 404:
                return None
            raise

        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        extensions = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
        if content_type not in extensions:
            raise BookOrbitApiError("cover download returned an unsupported image type")
        content = response.content
        if not content:
            raise BookOrbitApiError("cover download returned an empty image")
        if len(content) > 20 * 1024 * 1024:
            raise BookOrbitApiError("cover download exceeded the 20 MiB safety limit")
        extension = extensions[content_type]
        return CoverImage(content=content, content_type=content_type, filename=f"cover-{book_id}.{extension}")

    async def _request(self, method: str, path: str, *, operation: str, **kwargs: Any) -> httpx.Response:
        """Make one request while reducing errors to safe operational context."""

        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            raise BookOrbitApiError(operation, error.response.status_code) from error
        except httpx.HTTPError as error:
            raise BookOrbitApiError(operation) from error


@asynccontextmanager
async def bookorbit_client(base_url: str | AnyHttpUrl, api_key: str) -> AsyncIterator[BookOrbitClient]:
    """Construct and close a client for a short administrative probe."""

    client = BookOrbitClient(base_url, api_key)
    try:
        yield client
    finally:
        await client.aclose()
