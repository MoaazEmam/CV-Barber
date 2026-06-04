"""case-insensitive unique username

Replaces the plain (case-sensitive) unique index on users.username with a
functional unique index on lower(username), so usernames are unique regardless
of case ("John" == "john"). Mirrors the case-insensitive login lookup in
UserManager.authenticate.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Guard: a functional UNIQUE index can't be created if case-variant duplicate
    # usernames already exist. Detect them up front and fail with a clear,
    # actionable message instead of an opaque IntegrityError mid-migration.
    dupes = bind.execute(
        sa.text(
            "SELECT lower(username) AS uname, count(*) AS n "
            "FROM users GROUP BY lower(username) HAVING count(*) > 1"
        )
    ).fetchall()
    if dupes:
        listing = ", ".join(f"{row.uname!r} ({row.n} accounts)" for row in dupes)
        raise RuntimeError(
            "Cannot enforce case-insensitive usernames — resolve these duplicate "
            f"usernames first, then re-run the migration: {listing}"
        )

    op.drop_index("ix_users_username", table_name="users")
    op.create_index(
        "ix_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_users_username_lower", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=True)
