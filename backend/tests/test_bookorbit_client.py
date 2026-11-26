import json

import httpx
import pytest

from app.providers.events.bookorbit.client import BookOrbitApiError, BookOrbitClient


@pytest.mark.asyncio
async def test_queries_accessible_library_with_read_key_header() -> None:
    """The client uses the verified library route and never places keys in URLs."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/libraries/4/books"
        assert request.headers["authorization"] == "Bearer bok_test"
        assert "bok_test" not in str(request.url)
        assert json.loads(request.content) == {
            "sort": [{"field": "addedAt", "dir": "desc"}],
            "pagination": {"page": 0, "size": 200},
        }
        return httpx.Response(
            200,
            json={
                "items": [{"id": 9, "libraryId": 4, "title": "Example", "authors": [], "files": []}],
                "total": 1,
                "page": 0,
                "size": 200,
            },
        )

    client = BookOrbitClient("https://books.example", "bok_test", transport=httpx.MockTransport(handler))
    try:
        result = await client.query_library_books(4)
    finally:
        await client.aclose()

    assert result.items[0].id == 9
    assert result.items[0].library_id == 4


@pytest.mark.asyncio
async def test_missing_cover_is_not_an_error() -> None:
    """A missing source cover must not prevent a later notification."""

    client = BookOrbitClient(
        "https://books.example",
        "bok_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(404, json={"message": "Not found"})),
    )
    try:
        cover = await client.get_cover(99)
    finally:
        await client.aclose()

    assert cover is None


@pytest.mark.asyncio
async def test_source_errors_do_not_keep_response_body() -> None:
    """Operational errors contain status context only, not potentially sensitive bodies."""

    client = BookOrbitClient(
        "https://books.example",
        "bok_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="secret body must not escape")),
    )
    try:
        with pytest.raises(BookOrbitApiError, match="HTTP 401") as error:
            await client.get_identity()
    finally:
        await client.aclose()

    assert "secret body" not in str(error.value)
