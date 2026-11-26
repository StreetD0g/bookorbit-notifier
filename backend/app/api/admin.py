"""Opt-in administrator authentication and notification status endpoints."""

from hmac import compare_digest
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, SecretStr, StrictBool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.crypto import SecretCipher
from app.database.models import Book, DeliveryMode, Library, NotificationTemplate, Server, Webhook
from app.providers.events.bookorbit.client import BookOrbitApiError
from app.providers.events.bookorbit.factory import EncryptedBookOrbitClientFactory
from app.providers.notifications.discord.client import DiscordDeliveryError
from app.providers.notifications.discord.sender_profile import ProfileChoice, ProfileField, SenderProfile
from app.queue.worker import (
    DiscordNotificationSender,
    EncryptedWebhookTargetResolver,
    OutgoingNotification,
    WebhookTarget,
    _template_values,
    render_embed,
)
from app.services.authentication import AuthenticationService
from app.services.configuration import ConfigurationService, CreateServer, CreateTemplate, CreateWebhook, UpdateServer, UpdateWebhook
from app.services.notifications import NotificationAdministrationService
from app.services.sender_profiles import SenderProfileService
from app.templates.safe import ALLOWED_TEMPLATE_VARIABLES

router = APIRouter(prefix="/admin", tags=["administrator"])
_SESSION_COOKIE = "bookorbit_session"
_CSRF_COOKIE = "bookorbit_csrf"


class PasswordInput(BaseModel):
    password: SecretStr


class ChangePasswordInput(BaseModel):
    current_password: SecretStr
    new_password: SecretStr


class RetryInput(BaseModel):
    confirm_sent_resend: StrictBool = False


class ProfileFieldInput(BaseModel):
    choice: ProfileChoice
    value: str | None = None


class ProfileInput(BaseModel):
    username: ProfileFieldInput
    avatar_url: ProfileFieldInput


class PreviewInput(BaseModel):
    title: str = Field(max_length=512)
    description: str = Field(max_length=4000)
    footer: str | None = Field(default=None, max_length=512)


class ProfileScopeItem(BaseModel):
    id: int
    name: str
    server_name: str | None = None


class ProfileScopeList(BaseModel):
    libraries: list[ProfileScopeItem]
    webhooks: list[ProfileScopeItem]


class ServerInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: SecretStr
    public_url: str | None = Field(default=None, max_length=2048)
    scan_interval_seconds: int = Field(default=60, ge=30, le=86400)


class WebhookInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    webhook_url: SecretStr


class WebhookTestInput(BaseModel):
    library_id: int | None = Field(default=None, gt=0)


class ServerUpdateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scan_interval_seconds: int = Field(ge=30, le=86400)
    api_key: SecretStr | None = None


class WebhookUpdateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: StrictBool
    webhook_url: SecretStr | None = None
    confirm_destination_change: StrictBool = False


class EnabledInput(BaseModel):
    enabled: StrictBool


class LibraryRoutingInput(BaseModel):
    monitored: StrictBool
    webhook_ids: list[int] = Field(max_length=100)
    template_id: int | None = None


class LibraryDeliveryInput(BaseModel):
    delivery_mode: DeliveryMode
    batch_window_seconds: int = Field(ge=30, le=86400)
    daily_summary_time: str = Field(max_length=5)
    timezone: str = Field(max_length=64)


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title_template: str = Field(max_length=512)
    description_template: str = Field(max_length=4000)
    footer_template: str | None = Field(default=None, max_length=512)
    color: int = Field(default=0x2F855A, ge=0, le=0xFFFFFF)
    show_cover: StrictBool = True
    metadata_fields: list[str] = Field(default_factory=list, max_length=100)


def _template_command(payload: TemplateInput) -> CreateTemplate:
    return CreateTemplate(
        name=payload.name,
        title_template=payload.title_template,
        description_template=payload.description_template,
        footer_template=payload.footer_template,
        color=payload.color,
        show_cover=payload.show_cover,
        metadata_fields=tuple(payload.metadata_fields),
    )


def _configuration(request: Request) -> ConfigurationService:
    """Require a separate operator-provided encryption key before handling credentials."""

    encryption_key = get_settings().encryption_key
    if encryption_key is None:
        raise HTTPException(status_code=503, detail="Encryption key is not configured")
    try:
        cipher = SecretCipher(encryption_key.get_secret_value())
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Encryption key is invalid") from error
    return ConfigurationService(request.app.state.session_factory, cipher)


def _context(request: Request) -> tuple[AuthenticationService, str, bool]:
    """Fail closed unless the admin service and a canonical trusted origin are configured."""

    settings = get_settings()
    if not settings.admin_enabled or not hasattr(request.app.state, "session_factory"):
        raise HTTPException(status_code=404, detail="Not found")
    origin = settings.admin_origin or ""
    try:
        parsed = urlsplit(origin)
        host, port = parsed.hostname, parsed.port
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Administrator origin is not configured") from error
    is_loopback = host in {"localhost", "127.0.0.1", "::1"}
    if (
        not host
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in {"https", "http"}
        or (parsed.scheme == "http" and not is_loopback)
        or port == 0
        or origin != f"{parsed.scheme}://{parsed.netloc}"
    ):
        raise HTTPException(status_code=503, detail="Administrator origin is not configured")
    return AuthenticationService(request.app.state.session_factory), origin, parsed.scheme == "https"


def _require_origin(request: Request, expected: str) -> None:
    """Protect unauthenticated setup/login and state changes from cross-site requests."""

    if request.headers.get("origin") != expected:
        raise HTTPException(status_code=403, detail="Invalid request origin")


def _authenticated(request: Request, response: Response) -> AuthenticationService:
    auth, origin, _secure = _context(request)
    response.headers["Cache-Control"] = "no-store"
    token = request.cookies.get(_SESSION_COOKIE, "")
    mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
    if mutation:
        _require_origin(request, origin)
    if not auth.validate(token, csrf_token=request.headers.get("x-csrf-token"), require_csrf=mutation):
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(request: Request, response: Response, payload: PasswordInput, x_setup_token: str = Header(default="")) -> dict[str, str]:
    """Create the first administrator only when the operator supplied a setup token."""

    auth, origin, _secure = _context(request)
    _require_origin(request, origin)
    response.headers["Cache-Control"] = "no-store"
    configured = get_settings().setup_token
    secret = configured.get_secret_value() if configured is not None else ""
    if len(secret) < 32 or len(x_setup_token) > 1024 or not compare_digest(secret.encode("utf-8"), x_setup_token.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Setup is unavailable")
    try:
        auth.setup(payload.password.get_secret_value())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "configured"}


@router.post("/login")
def login(request: Request, response: Response, payload: PasswordInput) -> dict[str, str]:
    """Issue independent session and CSRF cookies after successful authentication."""

    auth, origin, secure = _context(request)
    _require_origin(request, origin)
    response.headers["Cache-Control"] = "no-store"
    credentials = auth.login(payload.password.get_secret_value())
    if credentials is None:
        raise HTTPException(status_code=401, detail="Login failed")
    options = {"secure": secure, "samesite": "strict", "path": "/", "max_age": 43_200}
    response.set_cookie(_SESSION_COOKIE, credentials.session_token, httponly=True, **options)
    response.set_cookie(_CSRF_COOKIE, credentials.csrf_token, httponly=False, **options)
    return {"status": "authenticated"}


@router.post("/logout")
def logout(request: Request, response: Response, auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> dict[str, str]:
    """Revoke the current session and remove its browser cookies."""

    auth.logout(request.cookies.get(_SESSION_COOKIE, ""))
    response.delete_cookie(_SESSION_COOKIE, path="/")
    response.delete_cookie(_CSRF_COOKIE, path="/")
    return {"status": "signed_out"}


@router.post("/change-password")
def change_password(
    request: Request, response: Response, payload: ChangePasswordInput, auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Change a local password after CSRF and current-password checks; revoke sessions."""

    try:
        changed = auth.change_password(
            request.cookies.get(_SESSION_COOKIE, ""), payload.current_password.get_secret_value(), payload.new_password.get_secret_value()
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not changed:
        raise HTTPException(status_code=401, detail="Password change failed")
    response.delete_cookie(_SESSION_COOKIE, path="/")
    response.delete_cookie(_CSRF_COOKIE, path="/")
    return {"status": "password_changed"}


@router.get("/notifications/summary")
def summary(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]):
    """Return queue counts without source or destination credentials."""

    return NotificationAdministrationService(request.app.state.session_factory).summary()


@router.get("/notifications")
def list_notifications(
    request: Request,
    _auth: Annotated[AuthenticationService, Depends(_authenticated)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List redacted delivery rows in bounded pages."""

    return NotificationAdministrationService(request.app.state.session_factory).list_deliveries(limit=limit, offset=offset)


@router.get("/notifications/{queue_item_id}/history")
def history(request: Request, queue_item_id: int, _auth: Annotated[AuthenticationService, Depends(_authenticated)]):
    """Return the redacted delivery history for one queue entry."""

    return NotificationAdministrationService(request.app.state.session_factory).history(queue_item_id)


@router.post("/notifications/{queue_item_id}/retry")
def retry(
    request: Request, queue_item_id: int, payload: RetryInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Retry a delivery only after authentication, origin and CSRF validation."""

    try:
        NotificationAdministrationService(request.app.state.session_factory).retry(
            queue_item_id, confirm_sent_resend=payload.confirm_sent_resend
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "queued"}


@router.get("/sender-profiles/{scope}")
def get_sender_profile(
    request: Request, scope: str, _auth: Annotated[AuthenticationService, Depends(_authenticated)], scope_id: int | None = None
) -> SenderProfile:
    """Read independent inheritance choices without exposing webhook credentials."""

    try:
        return SenderProfileService(request.app.state.session_factory).get(scope, scope_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/profile-scopes")
def profile_scopes(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> ProfileScopeList:
    """List names and IDs for profile selectors without returning encrypted credentials."""

    with request.app.state.session_factory() as session:
        libraries = session.execute(
            select(Library.id, Library.name, Server.name)
            .join(Server, Library.server_id == Server.id)
            .order_by(Server.name, Library.name, Library.id)
        ).all()
        webhooks = session.execute(select(Webhook.id, Webhook.name).order_by(Webhook.name, Webhook.id)).all()
        return ProfileScopeList(
            libraries=[ProfileScopeItem(id=row[0], name=row[1], server_name=row[2]) for row in libraries],
            webhooks=[ProfileScopeItem(id=row[0], name=row[1]) for row in webhooks],
        )


@router.get("/servers")
def list_servers(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> list[dict]:
    """List source configuration without returning the stored API key."""

    with request.app.state.session_factory() as session:
        servers = session.scalars(select(Server).order_by(Server.name, Server.id)).all()
        return [
            {
                "id": server.id,
                "name": server.name,
                "base_url": server.base_url,
                "enabled": server.enabled,
                "scan_interval_seconds": server.scan_interval_seconds,
            }
            for server in servers
        ]


@router.post("/servers", status_code=status.HTTP_201_CREATED)
def create_server(request: Request, payload: ServerInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]):
    """Persist a source key encrypted; discovery remains an explicit read-only action."""

    try:
        return _configuration(request).create_server(
            CreateServer(
                name=payload.name,
                base_url=payload.base_url,
                api_key=payload.api_key.get_secret_value(),
                public_url=payload.public_url,
                scan_interval_seconds=payload.scan_interval_seconds,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Server name already exists") from error


@router.put("/servers/{server_id}/enabled")
def set_server_enabled(
    request: Request, server_id: int, payload: EnabledInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Pause or resume scanning without deleting inventory or notification history."""

    with request.app.state.session_factory() as session, session.begin():
        server = session.get(Server, server_id)
        if server is None:
            raise HTTPException(status_code=404, detail="Server not found")
        server.enabled = payload.enabled
    return {"status": "saved"}


@router.put("/servers/{server_id}")
def update_server(
    request: Request, server_id: int, payload: ServerUpdateInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
):
    """Update a server without returning its existing or replacement API key."""

    try:
        return _configuration(request).update_server(
            server_id,
            UpdateServer(
                name=payload.name,
                scan_interval_seconds=payload.scan_interval_seconds,
                api_key=payload.api_key.get_secret_value() if payload.api_key is not None else None,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Server name already exists") from error


@router.post("/servers/{server_id}/scan")
async def scan_server(request: Request, server_id: int, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> dict:
    """Run a scoped manual read-only reconciliation when the scheduler is enabled."""

    scheduler = getattr(request.app.state, "runtime_scheduler", None)
    if not get_settings().runtime_enabled or scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not enabled")
    try:
        report = await scheduler.run_manual_scan(server_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Server is missing or disabled") from error
    if report.error or (report.scan is not None and any(library.error for library in report.scan.libraries)):
        raise HTTPException(status_code=502, detail="Server scan failed")
    return {"server_id": report.server_id, "scan": report.scan, "metadata": report.metadata}


@router.post("/servers/{server_id}/sync-libraries")
async def sync_libraries(
    request: Request, server_id: int, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, int]:
    """Synchronize accessible library names using the stored read-only API key."""

    service = _configuration(request)
    cipher = SecretCipher(get_settings().encryption_key.get_secret_value())  # type: ignore[union-attr]
    factory = EncryptedBookOrbitClientFactory(request.app.state.session_factory, cipher)
    try:
        async with factory.connect(server_id) as client:
            source_libraries = await client.list_libraries()
        result = service.synchronize_libraries(server_id, source_libraries)
    except (BookOrbitApiError, ValueError) as error:
        raise HTTPException(status_code=502, detail="Library discovery failed") from error
    return {"created": result.created, "updated": result.updated}


@router.get("/webhooks")
def list_webhooks(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> list[dict]:
    """Never include webhook URLs or ciphertext in the response."""

    with request.app.state.session_factory() as session:
        rows = session.scalars(select(Webhook).order_by(Webhook.name, Webhook.id)).all()
        return [{"id": row.id, "name": row.name, "enabled": row.enabled} for row in rows]


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
def create_webhook(request: Request, payload: WebhookInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]):
    """Validate an official Discord endpoint and persist its URL encrypted."""

    try:
        return _configuration(request).create_webhook(CreateWebhook(name=payload.name, webhook_url=payload.webhook_url.get_secret_value()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Webhook name already exists") from error


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    request: Request, webhook_id: int, payload: WebhookTestInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Send a fixed test message with resolved profile overrides, without modifying the webhook."""

    _configuration(request)
    if payload.library_id is not None:
        with request.app.state.session_factory() as session:
            library = session.get(Library, payload.library_id)
            if library is None or webhook_id not in {webhook.id for webhook in library.webhooks}:
                raise HTTPException(status_code=400, detail="Library is not routed to this webhook")
    cipher = SecretCipher(get_settings().encryption_key.get_secret_value())  # type: ignore[union-attr]
    try:
        target = EncryptedWebhookTargetResolver(request.app.state.session_factory, cipher).resolve(webhook_id)
        username, avatar_url = SenderProfileService(request.app.state.session_factory).resolve(payload.library_id or 0, webhook_id)
        target = WebhookTarget(webhook_id=target.webhook_id, webhook_url=target.webhook_url, username=username, avatar_url=avatar_url)
        await DiscordNotificationSender().send(
            target, OutgoingNotification(embed={"title": "BookOrbit Notifier", "description": "This is a test notification."})
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Webhook is unavailable") from error
    except DiscordDeliveryError as error:
        raise HTTPException(status_code=502, detail="Discord test delivery failed") from error
    return {"status": "sent"}


@router.put("/webhooks/{webhook_id}")
def update_webhook(
    request: Request, webhook_id: int, payload: WebhookUpdateInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
):
    """Rotate a locally stored URL only after acknowledging queued deliveries may be redirected."""

    try:
        return _configuration(request).update_webhook(
            webhook_id,
            UpdateWebhook(
                name=payload.name,
                enabled=payload.enabled,
                webhook_url=payload.webhook_url.get_secret_value() if payload.webhook_url is not None else None,
                confirm_destination_change=payload.confirm_destination_change,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Webhook name already exists") from error


@router.get("/libraries")
def list_libraries(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> list[dict]:
    """Return current routing by source IDs, with no source or destination secrets."""

    with request.app.state.session_factory() as session:
        rows = session.scalars(select(Library).order_by(Library.server_id, Library.name, Library.id)).all()
        return [
            {
                "id": row.id,
                "server_id": row.server_id,
                "name": row.name,
                "monitored": row.monitored,
                "webhook_ids": [webhook.id for webhook in row.webhooks],
                "template_id": row.template_id,
                "delivery_mode": row.delivery_mode,
                "batch_window_seconds": row.batch_window_seconds,
                "daily_summary_time": row.daily_summary_time,
                "timezone": row.timezone,
            }
            for row in rows
        ]


@router.put("/libraries/{library_id}/routing")
def configure_library_routing(
    request: Request, library_id: int, payload: LibraryRoutingInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Assign destinations while leaving the source library and its content untouched."""

    try:
        _configuration(request).configure_library_routing(
            library_id, monitored=payload.monitored, webhook_ids=payload.webhook_ids, template_id=payload.template_id
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "saved"}


@router.put("/libraries/{library_id}/delivery")
def configure_library_delivery(
    request: Request, library_id: int, payload: LibraryDeliveryInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    """Set the mode for future events; already scheduled rows keep their deadlines."""

    try:
        _configuration(request).configure_library_delivery(
            library_id,
            delivery_mode=payload.delivery_mode,
            batch_window_seconds=payload.batch_window_seconds,
            daily_summary_time=payload.daily_summary_time,
            timezone=payload.timezone,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "saved"}


@router.get("/template-variables")
def template_variables(_auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> list[str]:
    """Expose only the interpolation allowlist, never source metadata or credentials."""

    return sorted(ALLOWED_TEMPLATE_VARIABLES)


@router.get("/templates")
def list_templates(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> list[dict]:
    """List declarative templates without returning any source credentials."""

    with request.app.state.session_factory() as session:
        templates = session.scalars(select(NotificationTemplate).order_by(NotificationTemplate.name, NotificationTemplate.id)).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "title_template": row.title_template,
                "description_template": row.description_template,
                "footer_template": row.footer_template,
                "color": row.color,
                "show_cover": row.show_cover,
                "metadata_fields": row.metadata_fields,
                "enabled": row.enabled,
            }
            for row in templates
        ]


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_template(
    request: Request, payload: TemplateInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, int]:
    try:
        return {"id": _configuration(request).create_template(_template_command(payload))}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Template name already exists") from error


@router.put("/templates/{template_id}")
def update_template(
    request: Request, template_id: int, payload: TemplateInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]
) -> dict[str, str]:
    try:
        _configuration(request).update_template(template_id, _template_command(payload))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Template name already exists") from error
    return {"status": "saved"}


@router.post("/template-preview")
def template_preview(payload: PreviewInput, _auth: Annotated[AuthenticationService, Depends(_authenticated)]) -> dict:
    """Render deterministic sample metadata with the exact production renderer."""

    book = Book(
        title="The Example Book",
        authors_json=["Alex Example"],
        source_added_at="2026-11-26T12:00:00Z",
        source_updated_at="2026-11-26T13:00:00Z",
        metadata_json={
            "subtitle": "A sample story",
            "seriesName": "Example series",
            "seriesIndex": "2",
            "publishedYear": 2024,
            "originalPublishedYear": 2020,
            "publishedDate": "2024-05-10",
            "pageCount": 320,
            "language": "de",
            "authors": [{"name": "Alex Example"}],
            "genres": ["Fantasy"],
            "tags": ["Adventure"],
            "publisher": "Example Press",
            "isbn10": "0123456789",
            "isbn13": "9780123456789",
            "editionName": "Example edition",
            "rating": 4,
            "description": "A sample description.",
            "files": [{"format": "epub"}, {"format": "mp3"}],
            "audioMetadata": {"narrators": [{"name": "Sam Example"}], "durationSeconds": 28800, "abridged": False},
            "collections": [{"name": "Favorites"}],
        },
    )
    try:
        return render_embed(payload.title, payload.description, payload.footer, 0x2F855A, _template_values(book, "Books", "Example server"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/sender-profiles/{scope}")
def set_sender_profile(
    request: Request,
    scope: str,
    payload: ProfileInput,
    _auth: Annotated[AuthenticationService, Depends(_authenticated)],
    scope_id: int | None = None,
) -> dict[str, str]:
    """Save a scoped profile only after origin, session and CSRF checks."""

    try:
        profile = SenderProfile(
            username=ProfileField(payload.username.choice, payload.username.value),
            avatar_url=ProfileField(payload.avatar_url.choice, payload.avatar_url.value),
        )
        SenderProfileService(request.app.state.session_factory).configure(scope, scope_id, profile)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "saved"}
