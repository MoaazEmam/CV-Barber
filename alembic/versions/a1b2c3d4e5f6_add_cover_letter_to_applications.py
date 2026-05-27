"""add_cover_letter_to_applications

Revision ID: a1b2c3d4e5f6
Revises: 4c5f60097ff1
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4c5f60097ff1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable cover_letter column to applications table."""
    op.add_column('applications', sa.Column('cover_letter', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove cover_letter column from applications table."""
    op.drop_column('applications', 'cover_letter')
