"""Add notification templates and per-library template selection.

Revision ID: 0004_configuration_templates
Revises: 0003_notification_history
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_configuration_templates"
down_revision: str | Sequence[str] | None = "0003_notification_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create declarative templates before attaching an optional reference to each library."""

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("title_template", sa.String(length=512), nullable=False),
        sa.Column("description_template", sa.Text(), nullable=False),
        sa.Column("footer_template", sa.String(length=512), nullable=True),
        sa.Column("color", sa.Integer(), nullable=False),
        sa.Column("show_cover", sa.Boolean(), nullable=False),
        sa.Column("metadata_fields", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("libraries") as batch:
        batch.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_libraries_template_id", "notification_templates", ["template_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_libraries_template_id", "libraries", ["template_id"])


def downgrade() -> None:
    """Detach template selections before removing their table."""

    op.drop_index("ix_libraries_template_id", table_name="libraries")
    with op.batch_alter_table("libraries") as batch:
        batch.drop_constraint("fk_libraries_template_id", type_="foreignkey")
        batch.drop_column("template_id")
    op.drop_table("notification_templates")
