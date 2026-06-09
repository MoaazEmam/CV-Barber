"""add template_artifact and section_map to master_cvs

Caches the new format-preserving pipeline's per-dedup-hash artifacts: the
template (a .tex string for PDF inputs, or a JSON-serialised paragraph-index map
for DOCX) and the span->role section map produced once by the Tier 1 LLM.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("master_cvs", sa.Column("template_artifact", sa.Text(), nullable=True))
    op.add_column("master_cvs", sa.Column("section_map", JSONB(), nullable=True))


def downgrade():
    op.drop_column("master_cvs", "section_map")
    op.drop_column("master_cvs", "template_artifact")
