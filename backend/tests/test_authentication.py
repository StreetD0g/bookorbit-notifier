"""Authentication behavior with a local SQLite database and no real credentials."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.database.base import Base
from app.database.models import Administrator, AdministratorSession
from app.database.session import create_database_engine, create_session_factory
from app.services.authentication import AuthenticationService


@pytest.fixture
def auth(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield AuthenticationService(factory), factory
    engine.dispose()


def test_setup_stores_argon_hash_and_cannot_be_repeated(auth) -> None:
    service, factory = auth
    assert not service.is_configured()
    with pytest.raises(ValueError):
        service.setup("short")
    service.setup("a long local password")
    with pytest.raises(ValueError, match="already configured"):
        service.setup("another long password")
    with factory() as session:
        admin = session.get(Administrator, 1)
        assert admin is not None and admin.password_hash.startswith("$argon2id$")
        assert "a long local password" not in admin.password_hash


def test_session_csrf_expiration_and_logout(auth) -> None:
    service, factory = auth
    service.setup("a long local password")
    now = datetime(2026, 11, 26, tzinfo=UTC)
    assert service.login("incorrect", now=now) is None
    credentials = service.login("a long local password", now=now)
    assert credentials is not None
    assert credentials.session_token not in repr(credentials)
    assert service.validate(credentials.session_token, now=now)
    assert not service.validate(credentials.session_token, require_csrf=True, now=now)
    assert not service.validate(credentials.session_token, csrf_token="x" * 43, require_csrf=True, now=now)
    assert service.validate(credentials.session_token, csrf_token=credentials.csrf_token, require_csrf=True, now=now)
    assert not service.validate(credentials.session_token, now=credentials.expires_at)
    with factory() as session:
        stored = session.scalar(select(AdministratorSession))
        assert stored is not None
        assert stored.token_hash != credentials.session_token and stored.csrf_hash != credentials.csrf_token
    service.logout(credentials.session_token)
    assert not service.validate(credentials.session_token, now=now)


def test_lockout_persists_across_service_instances(auth) -> None:
    service, factory = auth
    service.setup("a long local password")
    now = datetime(2026, 11, 26, tzinfo=UTC)
    for _ in range(5):
        assert service.login("wrong password", now=now) is None
    restarted = AuthenticationService(factory)
    assert restarted.login("a long local password", now=now + timedelta(minutes=14)) is None
    assert restarted.login("a long local password", now=now + timedelta(minutes=15)) is not None
