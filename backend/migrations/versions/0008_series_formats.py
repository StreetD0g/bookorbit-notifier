"""Add independently configurable numbered and unnumbered series formats."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_series_formats"
down_revision: str | Sequence[str] | None = "0007_administrator_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Existing templates receive safe defaults without changing their selections."""

    op.add_column(
        "notification_templates",
        sa.Column("series_numbered_template", sa.String(512), nullable=False, server_default="Teil {{series_index}} von {{series}}"),
    )
    op.add_column(
        "notification_templates", sa.Column("series_unnumbered_template", sa.String(512), nullable=False, server_default="{{series}}")
    )


def downgrade() -> None:
    with op.batch_alter_table("notification_templates") as batch:
        batch.drop_column("series_unnumbered_template")
        batch.drop_column("series_numbered_template")
