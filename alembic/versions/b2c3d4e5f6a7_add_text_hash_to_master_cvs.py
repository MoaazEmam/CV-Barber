"""add_text_hash_to_master_cvs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("master_cvs", sa.Column("text_hash", sa.String(64), nullable=True))
    op.create_index("ix_master_cvs_text_hash", "master_cvs", ["text_hash"])
    op.create_index(
        "uq_master_cvs_user_text_hash",
        "master_cvs",
        ["user_id", "text_hash"],
        unique=True,
        postgresql_where=sa.text("text_hash IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_master_cvs_user_text_hash", table_name="master_cvs")
    op.drop_index("ix_master_cvs_text_hash", table_name="master_cvs")
    op.drop_column("master_cvs", "text_hash")
