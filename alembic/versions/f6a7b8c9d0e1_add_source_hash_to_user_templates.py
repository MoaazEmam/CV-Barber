"""add source_hash to user_templates

Dedup key for custom templates: a SHA-256 over the normalized original upload so
the same file isn't stored twice (and re-uploads skip the LLM conversion). Mirrors
the master_cvs.text_hash dedup (partial-unique per user, NULLs excluded).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_templates", sa.Column("source_hash", sa.String(64), nullable=True))
    op.create_index("ix_user_templates_source_hash", "user_templates", ["source_hash"])
    op.create_index(
        "uq_user_templates_user_source_hash",
        "user_templates",
        ["user_id", "source_hash"],
        unique=True,
        postgresql_where=sa.text("source_hash IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_user_templates_user_source_hash", table_name="user_templates")
    op.drop_index("ix_user_templates_source_hash", table_name="user_templates")
    op.drop_column("user_templates", "source_hash")
