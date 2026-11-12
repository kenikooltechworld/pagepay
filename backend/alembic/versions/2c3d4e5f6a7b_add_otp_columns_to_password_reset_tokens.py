"""add otp columns to password_reset_tokens (persisted forgot-password OTP)

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2c3d4e5f6a7b"
down_revision: Union[str, None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("password_reset_tokens"):
        return
    if not _has_column(insp, "password_reset_tokens", "otp_hash"):
        op.add_column("password_reset_tokens", sa.Column("otp_hash", sa.String(length=255), nullable=True))
    if not _has_column(insp, "password_reset_tokens", "otp_expires_at"):
        op.add_column("password_reset_tokens", sa.Column("otp_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # non-destructive
    pass
