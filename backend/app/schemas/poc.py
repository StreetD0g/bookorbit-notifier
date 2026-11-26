"""Schemas for intentionally guarded, non-persistent POC diagnostics."""

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr


class BookOrbitProbeRequest(BaseModel):
    """Transient source credentials used only while checking compatibility."""

    base_url: AnyHttpUrl
    api_key: SecretStr = Field(min_length=1)


class BookOrbitProbeResponse(BaseModel):
    """Redacted compatibility result returned to the local administrator."""

    authentication_method: str | None
    username: str | None
    library_count: int
    sampled_library_id: int | None
    sampled_book_id: int | None
    cover_status: str


class DiscordProbeRequest(BaseModel):
    """Transient Discord endpoint used only for a local test message."""

    webhook_url: SecretStr = Field(min_length=1)


class DiscordProbeResponse(BaseModel):
    """Safe delivery information without exposing a webhook URL."""

    message_id: str | None
    status_code: int
