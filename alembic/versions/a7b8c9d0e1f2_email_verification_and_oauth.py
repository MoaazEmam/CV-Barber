"""email verification codes, oauth accounts, nullable username

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy.dialects.postgresql import UUID

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Google-OAuth users have no username until they pick one.
    op.alter_column("users", "username", existing_type=sa.String(), nullable=True)

    op.create_table(
        "email_verification_codes",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(), nullable=False),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="1"),
    )

    # Mirrors fastapi-users' SQLAlchemyBaseOAuthAccountTableUUID columns.
    op.create_table(
        "oauth_account",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column("oauth_name", sa.String(100), nullable=False, index=True),
        sa.Column("access_token", sa.String(1024), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("refresh_token", sa.String(1024), nullable=True),
        sa.Column("account_id", sa.String(320), nullable=False, index=True),
        sa.Column("account_email", sa.String(320), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oauth_account")
    op.drop_table("email_verification_codes")
    op.alter_column("users", "username", existing_type=sa.String(), nullable=False)
