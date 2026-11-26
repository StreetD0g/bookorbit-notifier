"""Encrypted multi-server, library-routing, and safe-template configuration services."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher
from app.database.models import DeliveryMode, Library, NotificationTemplate, Server, Webhook
from app.schemas.bookorbit import BookOrbitLibrary
from app.templates.safe import (
    ALLOWED_TEMPLATE_VARIABLES,
    DEFAULT_SERIES_NUMBERED,
    DEFAULT_SERIES_UNNUMBERED,
    validate_series_format,
    validate_template_syntax,
)

type SessionFactory = Callable[[], Session]

_DISCORD_WEBHOOK_HOSTS = {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}


@dataclass(frozen=True, slots=True)
class CreateServer:
    """All sensitive creation inputs remain local to this service invocation."""

    name: str
    base_url: str
    api_key: str
    public_url: str | None = None
    enabled: bool = True
    scan_interval_seconds: int = 60
    timeout_seconds: int = 15
    verify_ssl: bool = True


@dataclass(frozen=True, slots=True)
class CreateWebhook:
    """Discord endpoint input; its URL is encrypted before any database write."""

    name: str
    webhook_url: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class UpdateServer:
    """Retain source identity and current key unless the operator supplies a replacement."""

    name: str
    scan_interval_seconds: int
    api_key: str | None = None
    public_url: str | None = None
    update_public_url: bool = False
    timeout_seconds: int | None = None
    verify_ssl: bool | None = None


@dataclass(frozen=True, slots=True)
class UpdateWebhook:
    """A replacement destination requires separate explicit confirmation."""

    name: str
    enabled: bool
    webhook_url: str | None = None
    confirm_destination_change: bool = False


@dataclass(frozen=True, slots=True)
class CreateTemplate:
    """Strictly declarative template fields; arbitrary Python/JavaScript is not supported."""

    name: str
    title_template: str = "{{title}}"
    description_template: str = "{{authors}}"
    footer_template: str | None = None
    color: int = 0x2F855A
    show_cover: bool = True
    metadata_fields: tuple[str, ...] = ()
    series_numbered_template: str = DEFAULT_SERIES_NUMBERED
    series_unnumbered_template: str = DEFAULT_SERIES_UNNUMBERED


@dataclass(frozen=True, slots=True)
class ServerView:
    """Redacted server representation that intentionally omits the API key."""

    id: int
    name: str
    base_url: str
    public_url: str | None
    enabled: bool
    scan_interval_seconds: int


@dataclass(frozen=True, slots=True)
class WebhookView:
    """Redacted webhook representation that intentionally omits its URL."""

    id: int
    name: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class LibrarySyncResult:
    """Counts for a source-library synchronization operation."""

    created: int
    updated: int


class ConfigurationService:
    """Own persistent configuration mutations until protected HTTP endpoints are introduced."""

    def __init__(self, session_factory: SessionFactory, cipher: SecretCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    def create_server(self, command: CreateServer) -> ServerView:
        """Create one normalized source server with its key encrypted at rest."""

        name = _required_text(command.name, "Server name", 120)
        base_url = _normalize_http_url(command.base_url, "BookOrbit base URL")
        public_url = _normalize_http_url(command.public_url, "Public BookOrbit URL") if command.public_url else None
        if not 30 <= command.scan_interval_seconds <= 86_400:
            raise ValueError("Scan interval must be between 30 seconds and 24 hours")
        if not 1 <= command.timeout_seconds <= 120:
            raise ValueError("Connection timeout must be between 1 and 120 seconds")
        encrypted_key = self._cipher.encrypt(_required_text(command.api_key, "BookOrbit API key", 512))
        with self._session_factory() as session:
            with session.begin():
                server = Server(
                    name=name,
                    base_url=base_url,
                    public_url=public_url,
                    api_key_encrypted=encrypted_key,
                    enabled=command.enabled,
                    scan_interval_seconds=command.scan_interval_seconds,
                    timeout_seconds=command.timeout_seconds,
                    verify_ssl=command.verify_ssl,
                )
                session.add(server)
                session.flush()
                return _server_view(server)

    def create_webhook(self, command: CreateWebhook) -> WebhookView:
        """Create a Discord destination without storing or returning its plaintext URL."""

        name = _required_text(command.name, "Webhook name", 120)
        webhook_url = _validate_discord_webhook_url(command.webhook_url)
        with self._session_factory() as session:
            with session.begin():
                webhook = Webhook(name=name, url_encrypted=self._cipher.encrypt(webhook_url), enabled=command.enabled)
                session.add(webhook)
                session.flush()
                return WebhookView(id=webhook.id, name=webhook.name, enabled=webhook.enabled)

    def update_server(self, server_id: int, command: UpdateServer) -> ServerView:
        """Edit display/interval and optionally rotate the key, preserving the source identity."""

        name = _required_text(command.name, "Server name", 120)
        if not 30 <= command.scan_interval_seconds <= 86_400:
            raise ValueError("Scan interval must be between 30 seconds and 24 hours")
        if command.timeout_seconds is not None and not 1 <= command.timeout_seconds <= 120:
            raise ValueError("Connection timeout must be between 1 and 120 seconds")
        public_url = _normalize_http_url(command.public_url, "Public BookOrbit URL") if command.public_url else None
        key = self._cipher.encrypt(_required_text(command.api_key, "BookOrbit API key", 512)) if command.api_key is not None else None
        with self._session_factory() as session, session.begin():
            server = session.get(Server, server_id)
            if server is None:
                raise ValueError("Server does not exist")
            server.name = name
            server.scan_interval_seconds = command.scan_interval_seconds
            if command.update_public_url:
                server.public_url = public_url
            if command.timeout_seconds is not None:
                server.timeout_seconds = command.timeout_seconds
            if command.verify_ssl is not None:
                server.verify_ssl = command.verify_ssl
            if key is not None:
                server.api_key_encrypted = key
            return _server_view(server)

    def update_webhook(self, webhook_id: int, command: UpdateWebhook) -> WebhookView:
        """Change local destination settings without calling Discord's modify API."""

        name = _required_text(command.name, "Webhook name", 120)
        url = _validate_discord_webhook_url(command.webhook_url) if command.webhook_url is not None else None
        if url is not None and not command.confirm_destination_change:
            raise ValueError("Changing the webhook destination requires explicit confirmation")
        with self._session_factory() as session, session.begin():
            webhook = session.get(Webhook, webhook_id)
            if webhook is None:
                raise ValueError("Webhook does not exist")
            webhook.name = name
            webhook.enabled = command.enabled
            if url is not None:
                webhook.url_encrypted = self._cipher.encrypt(url)
            return WebhookView(id=webhook.id, name=webhook.name, enabled=webhook.enabled)

    def create_template(self, command: CreateTemplate) -> int:
        """Persist a validated declarative template and return only its non-secret ID."""

        name = _validate_template(command)
        with self._session_factory() as session:
            with session.begin():
                template = NotificationTemplate(
                    name=name,
                    title_template=command.title_template,
                    description_template=command.description_template,
                    footer_template=command.footer_template,
                    color=command.color,
                    show_cover=command.show_cover,
                    metadata_fields=list(command.metadata_fields),
                    series_numbered_template=command.series_numbered_template,
                    series_unnumbered_template=command.series_unnumbered_template,
                )
                session.add(template)
                session.flush()
                return template.id

    def update_template(self, template_id: int, command: CreateTemplate) -> None:
        """Change the shared layout without altering assigned libraries."""

        name = _validate_template(command)
        with self._session_factory() as session, session.begin():
            template = session.get(NotificationTemplate, template_id)
            if template is None:
                raise ValueError("Notification template does not exist")
            template.name = name
            template.title_template = command.title_template
            template.description_template = command.description_template
            template.footer_template = command.footer_template
            template.color = command.color
            template.show_cover = command.show_cover
            template.metadata_fields = list(command.metadata_fields)
            template.series_numbered_template = command.series_numbered_template
            template.series_unnumbered_template = command.series_unnumbered_template

    def synchronize_libraries(self, server_id: int, source_libraries: Sequence[BookOrbitLibrary]) -> LibrarySyncResult:
        """Upsert accessible source libraries; absent source rows are never deleted automatically."""

        seen_ids: set[int] = set()
        for source_library in source_libraries:
            if source_library.id in seen_ids:
                raise ValueError("BookOrbit library list contains a duplicate ID")
            seen_ids.add(source_library.id)
        with self._session_factory() as session:
            with session.begin():
                server = session.get(Server, server_id)
                if server is None:
                    raise ValueError("Server does not exist")
                existing = {
                    library.bookorbit_library_id: library
                    for library in session.scalars(select(Library).where(Library.server_id == server_id)).all()
                }
                created = updated = 0
                for source_library in source_libraries:
                    library = existing.get(source_library.id)
                    if library is None:
                        session.add(Library(server_id=server_id, bookorbit_library_id=source_library.id, name=source_library.name))
                        created += 1
                    elif library.name != source_library.name:
                        library.name = source_library.name
                        updated += 1
                return LibrarySyncResult(created=created, updated=updated)

    def configure_library_routing(
        self,
        library_id: int,
        *,
        monitored: bool,
        webhook_ids: Sequence[int],
        template_id: int | None,
    ) -> None:
        """Assign zero or more independent Discord targets and an optional safe template."""

        requested_webhook_ids = list(dict.fromkeys(webhook_ids))
        with self._session_factory() as session:
            with session.begin():
                library = session.get(Library, library_id)
                if library is None:
                    raise ValueError("Library does not exist")
                webhooks = (
                    session.scalars(select(Webhook).where(Webhook.id.in_(requested_webhook_ids))).all() if requested_webhook_ids else []
                )
                if len(webhooks) != len(requested_webhook_ids):
                    raise ValueError("One or more requested webhooks do not exist")
                if template_id is not None and session.get(NotificationTemplate, template_id) is None:
                    raise ValueError("Notification template does not exist")
                library.monitored = monitored
                library.template_id = template_id
                library.webhooks = webhooks

    def configure_library_delivery(
        self,
        library_id: int,
        *,
        delivery_mode: DeliveryMode,
        batch_window_seconds: int = 300,
        daily_summary_time: str = "18:00",
        timezone: str = "Europe/Berlin",
    ) -> None:
        """Configure a library's durable aggregation behavior with strict local validation."""

        if not 30 <= batch_window_seconds <= 86_400:
            raise ValueError("Batch window must be between 30 seconds and 24 hours")
        normalized_time = _validate_daily_summary_time(daily_summary_time)
        normalized_timezone = _validate_timezone(timezone)
        with self._session_factory() as session:
            with session.begin():
                library = session.get(Library, library_id)
                if library is None:
                    raise ValueError("Library does not exist")
                library.delivery_mode = DeliveryMode(delivery_mode)
                library.batch_window_seconds = batch_window_seconds
                library.daily_summary_time = normalized_time
                library.timezone = normalized_timezone

    def list_servers(self) -> list[ServerView]:
        """List non-secret source configuration for future administrator views."""

        with self._session_factory() as session:
            servers = session.scalars(select(Server).order_by(Server.name)).all()
        return [_server_view(server) for server in servers]

    def list_webhooks(self) -> list[WebhookView]:
        """List non-secret webhook configuration for future administrator views."""

        with self._session_factory() as session:
            webhooks = session.scalars(select(Webhook).order_by(Webhook.name)).all()
        return [WebhookView(id=webhook.id, name=webhook.name, enabled=webhook.enabled) for webhook in webhooks]


def _required_text(value: str, label: str, max_length: int) -> str:
    """Normalize human-entered labels/credentials without silently accepting blanks."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} is required")
    if len(normalized) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return normalized


def _validate_template(command: CreateTemplate) -> str:
    """Validate template fields consistently on both creation and update."""

    name = _required_text(command.name, "Template name", 120)
    validate_series_format(command.series_numbered_template)
    validate_series_format(command.series_unnumbered_template)
    for field_name, value, limit in (
        ("Title template", command.title_template, 512),
        ("Description template", command.description_template, 4000),
        ("Footer template", command.footer_template, 512),
    ):
        if value is not None:
            if len(value) > limit:
                raise ValueError(f"{field_name} exceeds {limit} characters")
            validate_template_syntax(value, field_name)
    if not 0 <= command.color <= 0xFFFFFF:
        raise ValueError("Embed color must be a 24-bit RGB integer")
    if any(field not in ALLOWED_TEMPLATE_VARIABLES for field in command.metadata_fields):
        raise ValueError("Metadata field contains an unsupported template variable")
    if len(command.metadata_fields) > 25 or len(set(command.metadata_fields)) != len(command.metadata_fields):
        raise ValueError("Metadata fields must contain at most 25 distinct variables")
    return name


def _normalize_http_url(value: str, label: str) -> str:
    """Accept internal/private BookOrbit URLs safely without embedding credentials in them."""

    parsed = _parse_url(value, label)
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{label} must not contain a query string or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _validate_discord_webhook_url(value: str) -> str:
    """Require a canonical HTTPS Discord webhook endpoint before encrypting it."""

    parsed = _parse_url(value, "Discord webhook URL")
    if parsed.scheme != "https" or parsed.hostname not in _DISCORD_WEBHOOK_HOSTS:
        raise ValueError("Discord webhook URL must use an official Discord HTTPS host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Discord webhook URL must not contain credentials, query strings, or fragments")
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 4 or path_parts[:2] != ["api", "webhooks"]:
        raise ValueError("Discord webhook URL has an unexpected path")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _parse_url(value: str, label: str) -> SplitResult:
    """Parse an HTTP(S) URL and reject malformed addresses before they reach HTTP clients."""

    if len(value) > 2048:
        raise ValueError(f"{label} exceeds 2048 characters")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{label} must be an absolute HTTP(S) URL")
    try:
        _ = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} has an invalid port") from error
    return parsed


def _validate_daily_summary_time(value: str) -> str:
    """Accept a fixed 24-hour local time without locale-dependent parsing."""

    normalized = value.strip()
    parts = normalized.split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError("Daily summary time must use HH:MM")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Daily summary time must use HH:MM")
    return f"{hour:02d}:{minute:02d}"


def _validate_timezone(value: str) -> str:
    """Ensure schedules use an installed IANA timezone, never an arbitrary string."""

    normalized = _required_text(value, "Timezone", 64)
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Timezone is not available") from error
    return normalized


def _server_view(server: Server) -> ServerView:
    """Create a redacted server DTO that cannot accidentally expose encrypted key material."""

    return ServerView(
        id=server.id,
        name=server.name,
        base_url=server.base_url,
        public_url=server.public_url,
        enabled=server.enabled,
        scan_interval_seconds=server.scan_interval_seconds,
    )
