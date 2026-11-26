"""Shared declarative base for Alembic metadata and ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The single metadata registry owned by the notifier."""
