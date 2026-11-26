"""Local administrator authentication; HTTP cookie policy belongs to the API layer."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Administrator, AdministratorSession

type SessionFactory = Callable[[], Session]

_MAX_FAILURES = 5
_LOCKOUT = timedelta(minutes=15)
_SESSION_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    """Transient secrets for secure HTTP cookies and CSRF form/header transport."""

    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    expires_at: datetime


class AuthenticationService:
    """Single-account setup, persistent login throttling, and revocable sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory
        self._hasher = PasswordHasher()

    def is_configured(self) -> bool:
        with self._sessions() as session:
            return session.get(Administrator, 1) is not None

    def setup(self, password: str) -> None:
        """Set the initial password once; the singleton primary key prevents setup races."""

        _validate_password(password)
        password_hash = self._hasher.hash(password)
        try:
            with self._sessions() as session, session.begin():
                session.add(Administrator(id=1, password_hash=password_hash))
        except IntegrityError as error:
            raise ValueError("Administrator is already configured") from error

    def login(self, password: str, *, now: datetime | None = None) -> SessionCredentials | None:
        """Serialize attempts in SQLite so concurrent failures cannot bypass the lockout."""

        if not isinstance(password, str) or len(password) > 1024:
            return None
        timestamp = _utc(now)
        with self._sessions() as session:
            # SQLite's write reservation prevents lost counter updates across processes.
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                admin = session.get(Administrator, 1)
                if admin is None or (admin.locked_until is not None and _utc(admin.locked_until) > timestamp):
                    session.commit()
                    return None
                try:
                    valid = self._hasher.verify(admin.password_hash, password)
                except VerificationError:
                    valid = False
                if not valid:
                    admin.failed_attempts += 1
                    if admin.failed_attempts >= _MAX_FAILURES:
                        admin.failed_attempts = 0
                        admin.locked_until = timestamp + _LOCKOUT
                    session.commit()
                    return None
                if self._hasher.check_needs_rehash(admin.password_hash):
                    admin.password_hash = self._hasher.hash(password)
                admin.failed_attempts = 0
                admin.locked_until = None
                credentials = SessionCredentials(token_urlsafe(32), token_urlsafe(32), timestamp + _SESSION_LIFETIME)
                session.execute(delete(AdministratorSession).where(AdministratorSession.expires_at <= timestamp))
                session.add(
                    AdministratorSession(
                        token_hash=_digest(credentials.session_token),
                        csrf_hash=_digest(credentials.csrf_token),
                        expires_at=credentials.expires_at,
                    )
                )
                session.commit()
                return credentials
            except Exception:
                session.rollback()
                raise

    def validate(self, token: str, *, csrf_token: str | None = None, require_csrf: bool = False, now: datetime | None = None) -> bool:
        """Validate an unexpired session and, for mutations, its independent CSRF token."""

        if not _valid_token(token) or (require_csrf and not _valid_token(csrf_token)):
            return False
        with self._sessions() as session:
            stored = session.get(AdministratorSession, _digest(token))
            if stored is None or _utc(stored.expires_at) <= _utc(now):
                return False
            return not require_csrf or compare_digest(stored.csrf_hash, _digest(csrf_token))  # type: ignore[arg-type]

    def logout(self, token: str) -> None:
        """Invalidate one session without revealing whether it existed."""

        if _valid_token(token):
            with self._sessions() as session, session.begin():
                session.execute(delete(AdministratorSession).where(AdministratorSession.token_hash == _digest(token)))


def _valid_token(value: str | None) -> bool:
    return isinstance(value, str) and 32 <= len(value) <= 128 and value.isascii()


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    # SQLite stores UTC datetimes without a timezone offset.
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
        raise ValueError("Password must contain between 12 and 1024 characters")
