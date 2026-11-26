"""Asynchronous Discord delivery worker over the persistent outbox state machine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher
from app.database.models import Book, Event, Webhook
from app.providers.notifications.discord.client import DiscordDeliveryError, DiscordWebhookClient
from app.queue.state import DeliveryClaim, claim_due_deliveries, record_delivery_failure, record_delivery_success, recover_stale_sends
from app.schemas.bookorbit import CoverImage
from app.templates.safe import render_template

type SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class WebhookTarget:
    """Decrypted destination used only in memory for the duration of one delivery."""

    webhook_id: int
    webhook_url: str


@dataclass(frozen=True, slots=True)
class OutgoingNotification:
    """Transport-ready embed plus an optional safe Discord attachment."""

    embed: dict[str, Any]
    cover: CoverImage | None = None


@dataclass(frozen=True, slots=True)
class DeliveryWorkerReport:
    """Outcome of one bounded worker pass without any secret-bearing context."""

    recovered_stale: int
    claimed: int
    sent: int
    retried: int
    failed: int


class WebhookTargetResolver(Protocol):
    """Resolve a stored destination at the point it is needed for delivery."""

    def resolve(self, webhook_id: int) -> WebhookTarget:
        """Return a transient webhook target or raise a safe configuration error."""


class NotificationBuilder(Protocol):
    """Build a transport payload from a durable event without exposing database internals."""

    def build(self, event_id: int) -> OutgoingNotification:
        """Return one sendable notification for a metadata-ready event."""


class NotificationSender(Protocol):
    """Delivery transport implemented by Discord today and other providers later."""

    async def send(self, target: WebhookTarget, notification: OutgoingNotification) -> tuple[str | None, int]:
        """Send one message and return Discord's message ID plus response status."""


class EncryptedWebhookTargetResolver:
    """Fetch and decrypt a configured Discord URL without ever serializing it to responses."""

    def __init__(self, session_factory: SessionFactory, cipher: SecretCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    def resolve(self, webhook_id: int) -> WebhookTarget:
        """Resolve one enabled webhook in a short local database session."""

        with self._session_factory() as session:
            webhook = session.get(Webhook, webhook_id)
            if webhook is None or not webhook.enabled:
                raise ValueError("Webhook is missing or disabled")
            return WebhookTarget(webhook_id=webhook.id, webhook_url=self._cipher.decrypt(webhook.url_encrypted))


class DefaultEmbedBuilder:
    """Temporary safe renderer until Phase 3 introduces configurable templates."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def build(self, event_id: int) -> OutgoingNotification:
        """Render a library template when configured, otherwise use the safe fallback embed."""

        with self._session_factory() as session:
            event = session.get(Event, event_id)
            if event is None:
                raise ValueError("Event does not exist")
            book = event.book
            library = book.library
            authors = ", ".join(book.authors_json)
            template = library.template if library.template and library.template.enabled else None
            if template is not None:
                values = _template_values(book, library.name, book.server.name)
                embed: dict[str, Any] = {
                    "title": render_template(template.title_template, values),
                    "description": render_template(template.description_template, values),
                    "color": template.color,
                }
                if template.footer_template:
                    embed["footer"] = {"text": render_template(template.footer_template, values)}
                return OutgoingNotification(embed=embed)
            description = authors or "New media detected in BookOrbit"
            return OutgoingNotification(
                embed={
                    "title": book.title or "New in the library",
                    "description": description,
                    "footer": {"text": "BookOrbit Notifier"},
                }
            )


def _template_values(book: Book, library_name: str, server_name: str) -> dict[str, object]:
    """Map stored BookOrbit metadata into documented template variables only."""

    metadata = book.metadata_json
    return {
        "title": book.title,
        "subtitle": metadata.get("subtitle"),
        "authors": book.authors_json,
        "series": metadata.get("seriesName"),
        "series_index": metadata.get("seriesIndex"),
        "library": library_name,
        "server": server_name,
        "genres": metadata.get("genres"),
        "language": metadata.get("language"),
        "formats": [file.get("format") for file in metadata.get("files", []) if isinstance(file, dict)],
        "narrators": metadata.get("audioMetadata", {}).get("narrators") if isinstance(metadata.get("audioMetadata"), dict) else None,
        "duration": metadata.get("audioMetadata", {}).get("durationSeconds") if isinstance(metadata.get("audioMetadata"), dict) else None,
        "description": metadata.get("description"),
        "isbn": metadata.get("isbn13"),
        "publisher": metadata.get("publisher"),
        "published_date": metadata.get("publishedDate"),
        "page_count": metadata.get("pageCount"),
        "age_rating": metadata.get("ageRating"),
        "content_warnings": metadata.get("contentWarnings"),
        "date_added": book.source_added_at,
        "book_url": "",
        "cover_url": "",
    }


class DiscordNotificationSender:
    """Production transport adapter; each client is closed before the next queue item."""

    async def send(self, target: WebhookTarget, notification: OutgoingNotification) -> tuple[str | None, int]:
        """Transmit an embed and optional attachment without forwarding BookOrbit credentials."""

        client = DiscordWebhookClient(target.webhook_url)
        try:
            return await client.send_embed(notification.embed, cover=notification.cover)
        finally:
            await client.aclose()


class DiscordDeliveryWorker:
    """Claim committed queue rows, perform HTTP I/O, then persist each target outcome."""

    def __init__(
        self,
        session_factory: SessionFactory,
        target_resolver: WebhookTargetResolver,
        notification_builder: NotificationBuilder,
        sender: NotificationSender | None = None,
        *,
        stale_after: timedelta = timedelta(minutes=5),
        max_attempts: int = 8,
    ) -> None:
        if stale_after.total_seconds() <= 0:
            raise ValueError("Stale-send interval must be positive")
        if max_attempts < 1:
            raise ValueError("Maximum attempts must be positive")
        self._session_factory = session_factory
        self._target_resolver = target_resolver
        self._notification_builder = notification_builder
        self._sender = sender or DiscordNotificationSender()
        self._stale_after = stale_after
        self._max_attempts = max_attempts

    async def process_once(self, *, limit: int = 20, now: datetime | None = None) -> DeliveryWorkerReport:
        """Process a small committed batch; a crash cannot lose source detection state."""

        timestamp = now or datetime.now(UTC)
        recovered = self._recover_stale(timestamp)
        claims = self._claim_due(limit, timestamp)
        sent = retried = failed = 0
        for claim in claims:
            outcome = await self._deliver_claim(claim, timestamp)
            if outcome == "sent":
                sent += 1
            elif outcome == "failed":
                failed += 1
            else:
                retried += 1
        return DeliveryWorkerReport(recovered_stale=recovered, claimed=len(claims), sent=sent, retried=retried, failed=failed)

    def _recover_stale(self, now: datetime) -> int:
        """Commit recovery first, so a fresh claim sees the recovered work."""

        with self._session_factory() as session:
            with session.begin():
                return recover_stale_sends(session, stale_after=self._stale_after, now=now)

    def _claim_due(self, limit: int, now: datetime) -> list[DeliveryClaim]:
        """Commit `SENDING` state before the first outbound HTTP request."""

        with self._session_factory() as session:
            with session.begin():
                return claim_due_deliveries(session, limit=limit, now=now)

    async def _deliver_claim(self, claim: DeliveryClaim, now: datetime) -> str:
        """Send one target and reduce every failure to a redacted persistent state."""

        try:
            target = self._target_resolver.resolve(claim.webhook_id)
            notification = self._notification_builder.build(claim.event_id)
            message_id, _status_code = await self._sender.send(target, notification)
        except DiscordDeliveryError as error:
            self._record_failure(claim, _discord_error_summary(error), error.retry_after_seconds, now)
            return "failed" if claim.attempt_count >= self._max_attempts else "retry"
        except Exception as error:
            # Do not persist arbitrary exception messages: adapters can include URLs or tokens.
            self._record_failure(claim, f"Delivery adapter failed ({type(error).__name__})", None, now)
            return "failed" if claim.attempt_count >= self._max_attempts else "retry"

        with self._session_factory() as session:
            with session.begin():
                record_delivery_success(session, queue_item_id=claim.queue_item_id, discord_message_id=message_id, sent_at=now)
        return "sent"

    def _record_failure(self, claim: DeliveryClaim, summary: str, retry_after_seconds: float | None, now: datetime) -> None:
        """Persist a retry/final failure for exactly the claimed webhook row."""

        with self._session_factory() as session:
            with session.begin():
                record_delivery_failure(
                    session,
                    queue_item_id=claim.queue_item_id,
                    error_summary=summary,
                    retry_after_seconds=retry_after_seconds,
                    max_attempts=self._max_attempts,
                    now=now,
                )


def _discord_error_summary(error: DiscordDeliveryError) -> str:
    """Persist only the response category, never Discord's untrusted response body."""

    return f"Discord delivery failed (HTTP {error.status_code})" if error.status_code is not None else "Discord delivery failed"
