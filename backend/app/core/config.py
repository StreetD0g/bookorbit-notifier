"""Runtime settings that are safe to load before persistent configuration exists."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-controlled settings for the proof-of-concept service.

    The flag defaults to disabled: POC routes accept transient source credentials and
    are intended only for an operator's local diagnostic session.
    """

    model_config = SettingsConfigDict(env_prefix="BOOKORBIT_NOTIFIER_", extra="ignore")

    poc_endpoints_enabled: bool = False
    database_url: str = "sqlite:///./data/bookorbit-notifier.db"
    encryption_key: SecretStr | None = None
    runtime_enabled: bool = False
    admin_enabled: bool = False
    admin_origin: str | None = None
    setup_token: SecretStr | None = None
    log_directory: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""

    return Settings()
