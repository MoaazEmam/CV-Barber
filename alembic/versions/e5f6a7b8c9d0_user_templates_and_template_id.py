"""add user_templates table and applications.template_id

Stores per-user custom CV templates (.html/.tex) and records each application's
chosen output template. Part of the deterministic template-system pivot that
replaced the vision LaTeX step.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("template_id", sa.String(), nullable=True))
    op.create_table(
        "user_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_templates_user_id", "user_templates", ["user_id"])


def downgrade():
    op.drop_index("ix_user_templates_user_id", table_name="user_templates")
    op.drop_table("user_templates")
    op.drop_column("applications", "template_id")
