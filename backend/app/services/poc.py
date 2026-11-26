"""Non-persistent orchestration for Phase-1 compatibility probes."""

from app.providers.events.bookorbit.client import BookOrbitClient
from app.providers.notifications.discord.client import DiscordWebhookClient
from app.schemas.poc import BookOrbitProbeResponse, DiscordProbeResponse


async def probe_bookorbit(client: BookOrbitClient) -> BookOrbitProbeResponse:
    """Exercise the least-privileged source operations without persisting secrets."""

    identity = await client.get_identity()
    libraries = await client.list_libraries()
    if not libraries:
        return BookOrbitProbeResponse(
            authentication_method=identity.authentication_method,
            username=identity.username,
            library_count=0,
            sampled_library_id=None,
            sampled_book_id=None,
            cover_status="not_checked_no_accessible_library",
        )

    library = libraries[0]
    books = await client.query_library_books(library.id, page=0, size=1)
    if not books.items:
        return BookOrbitProbeResponse(
            authentication_method=identity.authentication_method,
            username=identity.username,
            library_count=len(libraries),
            sampled_library_id=library.id,
            sampled_book_id=None,
            cover_status="not_checked_empty_library",
        )

    book = books.items[0]
    # Fetching detail verifies that an inventory ID can be resolved without write access.
    await client.get_book(book.id)
    cover = await client.get_cover(book.id)
    return BookOrbitProbeResponse(
        authentication_method=identity.authentication_method,
        username=identity.username,
        library_count=len(libraries),
        sampled_library_id=library.id,
        sampled_book_id=book.id,
        cover_status="available" if cover is not None else "not_available",
    )


async def send_discord_probe(client: DiscordWebhookClient) -> DiscordProbeResponse:
    """Send a fixed non-book message to prove webhook reachability."""

    message_id, status_code = await client.send_embed(
        {
            "title": "BookOrbit Notifier connection test",
            "description": "The Discord webhook accepted a test message.",
            "footer": {"text": "BookOrbit Notifier"},
        }
    )
    return DiscordProbeResponse(message_id=message_id, status_code=status_code)
