"""Opt-in administrator authentication and notification status endpoints."""

from hmac import compare_digest
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, SecretStr, StrictBool

from app.core.config import get_settings
from app.providers.notifications.discord.sender_profile import ProfileChoice, ProfileField, SenderProfile
from app.services.authentication import AuthenticationService
from app.services.notifications import NotificationAdministrationService
from app.services.sender_profiles import SenderProfileService

router = APIRouter(prefix="/admin", tags=["administrator"])
_SESSION_COOKIE = "bookorbit_session"
_CSRF_COOKIE = "bookorbit_csrf"


class PasswordInput(BaseModel):
    password: SecretStr


class RetryInput(BaseModel):
    confirm_sent_resend: StrictBool = False


class ProfileFieldInput(BaseModel):
    choice: ProfileChoice
    value: str | None = None


class ProfileInput(BaseModel):
    username: ProfileFieldInput
    avatar_url: ProfileFieldInput


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


@router.get("/notifications/summary")
def summary(request: Request, _auth: Annotated[AuthenticationService, Depends(_authenticated)]):
    """Return queue counts without source or destination credentials."""

    return NotificationAdministrationService(request.app.state.session_factory).summary()


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
