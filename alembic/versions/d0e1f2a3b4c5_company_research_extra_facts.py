"""company_research extra_research + extra_topics (Q&A gap lookups)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_research", sa.Column("extra_research", sa.Text(), nullable=True))
    op.add_column("company_research", sa.Column("extra_topics", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_research", "extra_topics")
    op.drop_column("company_research", "extra_research")
