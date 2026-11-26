"""Narrow models for fields verified in the current BookOrbit source.

BookOrbit does not promise a stable third-party API. Unknown source fields are
accepted so that harmless upstream additions do not break the notifier, while the
application uses only the explicitly modelled fields.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceModel(BaseModel):
    """Base model that tolerates source fields added by BookOrbit."""

    model_config = ConfigDict(extra="allow")


class BookOrbitLibrary(SourceModel):
    """Accessible BookOrbit library returned by `GET /libraries`."""

    id: int
    name: str
    book_count: int | None = Field(default=None, alias="bookCount")


class BookOrbitFile(SourceModel):
    """A logical book's file summary; a book can have several files."""

    id: int
    format: str | None = None
    role: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")


class BookOrbitBookCard(SourceModel):
    """Book list card used for polling and stable source identity."""

    id: int
    library_id: int | None = Field(default=None, alias="libraryId")
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    files: list[BookOrbitFile] = Field(default_factory=list)
    added_at: str | None = Field(default=None, alias="addedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    has_cover: bool | None = Field(default=None, alias="hasCover")
    cover_version: str | None = Field(default=None, alias="coverVersion")


class BookOrbitBookPage(SourceModel):
    """Zero-based paginated response from a BookOrbit book query."""

    items: list[BookOrbitBookCard]
    total: int
    page: int
    size: int
    book_total: int | None = Field(default=None, alias="bookTotal")


class BookOrbitBookDetail(SourceModel):
    """Fields used by the later metadata and embed builders."""

    id: int
    library_id: int = Field(alias="libraryId")
    library_name: str = Field(alias="libraryName")
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    authors: list[dict[str, Any]] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    language: str | None = None
    publisher: str | None = None
    published_date: str | None = Field(default=None, alias="publishedDate")
    isbn13: str | None = None
    page_count: int | None = Field(default=None, alias="pageCount")
    added_at: str = Field(alias="addedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    files: list[BookOrbitFile] = Field(default_factory=list)


class BookOrbitIdentity(SourceModel):
    """Non-secret subset of `/auth/me` that proves API-key authentication."""

    id: int | None = None
    username: str | None = None
    authentication_method: str | None = Field(default=None, alias="authenticationMethod")
    permissions: list[str] = Field(default_factory=list)


class CoverImage(BaseModel):
    """Validated image data ready for a Discord multipart attachment."""

    content: bytes
    content_type: str
    filename: str
