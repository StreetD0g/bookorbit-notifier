from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import Book, Event, EventStatus, Library, NotificationTemplate, Server
from app.queue.worker import DefaultEmbedBuilder
from app.templates.safe import render_template, validate_template_syntax


def test_safe_template_renderer_interpolates_only_documented_values() -> None:
    """Missing values stay blank and template code is never evaluated."""

    assert render_template("{{title}} — {{authors}}", {"title": "Book", "authors": ["A", "B"]}) == "Book — A, B"
    assert render_template("{{subtitle}}", {}) == ""
    with pytest.raises(ValueError, match="unsupported template syntax"):
        validate_template_syntax("{% import os %}", "Template")


def test_default_embed_builder_uses_library_template(tmp_path: Path) -> None:
    """Configured library templates affect an actual worker payload without executable code."""

    engine = create_engine(f"sqlite:///{tmp_path / 'templates.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        server = Server(name="Source", base_url="https://books.example", api_key_encrypted="encrypted")
        template = NotificationTemplate(
            name="Custom",
            title_template="New: {{title}}",
            description_template="{{authors}} in {{library}}",
            footer_template="{{server}}",
            color=0x112233,
        )
        library = Library(server=server, bookorbit_library_id=1, name="Books", template=template)
        book = Book(server=server, library=library, bookorbit_book_id=1, title="Arrival", authors_json=["Author"], metadata_json={})
        event = Event(server_id=1, library_id=1, book=book, event_type="BOOK_ADDED", status=EventStatus.READY)
        session.add_all([server, template, library, book, event])
        session.commit()
        event_id = event.id

    builder = DefaultEmbedBuilder(lambda: Session(engine))
    notification = builder.build(event_id)

    assert notification.embed == {
        "title": "New: Arrival",
        "description": "Author in Books",
        "color": 0x112233,
        "footer": {"text": "Source"},
    }
    engine.dispose()
