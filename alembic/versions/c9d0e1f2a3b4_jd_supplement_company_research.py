"""jd_supplement column + company_research cache table

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("jd_supplement", sa.Text(), nullable=True))
    op.create_table(
        "company_research",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_key", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("research", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("company_research")
    op.drop_column("applications", "jd_supplement")
