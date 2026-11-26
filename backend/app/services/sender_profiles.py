"""Persist and resolve independent Discord sender profiles."""

from collections.abc import Callable
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.database.models import Library, SenderProfileConfig, Webhook
from app.providers.notifications.discord.sender_profile import DEFAULT_PROFILE, ProfileChoice, ProfileField, SenderProfile, resolve_profile

type SessionFactory = Callable[[], Session]


class SenderProfileService:
    """Keep sender preferences local; no Discord webhook modification is performed."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def configure(self, scope: str, scope_id: int | None, profile: SenderProfile) -> None:
        """Validate and persist an entire scope atomically."""

        key = _scope_key(scope, scope_id)
        _validate_profile(profile)
        with self._session_factory() as session, session.begin():
            if scope == "library" and session.get(Library, scope_id) is None:
                raise ValueError("Library does not exist")
            if scope == "webhook" and session.get(Webhook, scope_id) is None:
                raise ValueError("Webhook does not exist")
            row = session.get(SenderProfileConfig, key)
            if row is None:
                row = SenderProfileConfig(scope_key=key)
                session.add(row)
            row.username_choice = profile.username.choice.value
            row.username_value = profile.username.value
            row.avatar_choice = profile.avatar_url.choice.value
            row.avatar_value = profile.avatar_url.value

    def resolve(self, library_id: int, webhook_id: int) -> tuple[str | None, str | None]:
        """Resolve from current settings; absent scopes inherit the built-in default."""

        with self._session_factory() as session:
            library = _load(session, f"library:{library_id}", SenderProfile())
            webhook = _load(session, f"webhook:{webhook_id}", SenderProfile())
            global_profile = _load(session, "global", DEFAULT_PROFILE)
            return resolve_profile(library, webhook, global_profile)


def _scope_key(scope: str, scope_id: int | None) -> str:
    if scope == "global" and scope_id is None:
        return scope
    if scope in {"library", "webhook"} and isinstance(scope_id, int) and not isinstance(scope_id, bool) and scope_id > 0:
        return f"{scope}:{scope_id}"
    raise ValueError("Invalid sender profile scope")


def _load(session: Session, key: str, default: SenderProfile) -> SenderProfile:
    row = session.get(SenderProfileConfig, key)
    if row is None:
        return default
    return SenderProfile(
        username=ProfileField(ProfileChoice(row.username_choice), row.username_value),
        avatar_url=ProfileField(ProfileChoice(row.avatar_choice), row.avatar_value),
    )


def _validate_profile(profile: SenderProfile) -> None:
    if profile.username.value is not None and (
        len(profile.username.value) > 80 or profile.username.value != profile.username.value.strip()
    ):
        raise ValueError("Sender name must be at most 80 characters without surrounding whitespace")
    value = profile.avatar_url.value
    if value is None:
        return
    if len(value) > 2048 or any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError("Avatar URL is invalid")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("Avatar URL is invalid") from error
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment or port not in (None, 443):
        raise ValueError("Avatar URL must be a public HTTPS URL")
    # Literal private IPs and local hostnames cannot be fetched by Discord. DNS
    # availability is deliberately not asserted: it can change after validation.
    try:
        address = ip_address(host)
    except ValueError:
        if "." not in host or host.lower().endswith((".local", ".localhost", ".internal")):
            raise ValueError("Avatar URL must use a public hostname") from None
    else:
        if not address.is_global:
            raise ValueError("Avatar URL must use a public address")
