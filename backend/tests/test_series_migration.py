"""Verify existing user templates survive the series-format schema migration."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_series_migration_preserves_existing_template(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{(tmp_path / 'before.db').as_posix()}"
    monkeypatch.setenv("BOOKORBIT_NOTIFIER_DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "migrations"))
    command.upgrade(config, "0007_administrator_auth")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO notification_templates
              (name, title_template, description_template, color, show_cover, metadata_fields, enabled, created_at, updated_at)
            VALUES ('Existing', '{{title}}', '{{authors}}', 1, 1, '[]', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name, series_numbered_template, series_unnumbered_template FROM notification_templates")
        ).one()
        assert row == ("Existing", "Teil {{series_index}} von {{series}}", "{{series}}")
    engine.dispose()
