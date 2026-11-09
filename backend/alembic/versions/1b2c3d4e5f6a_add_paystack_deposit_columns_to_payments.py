"""add paystack deposit columns to payments (compat with existing table)

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "1b2c3d4e5f6a"
down_revision: Union[str, None] = "0a1b2c3d4e5f"
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
    if not insp.has_table("payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("purpose", sa.String(length=50), nullable=True, index=True),
            sa.Column("tier", sa.String(length=50), nullable=True),
            sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
            sa.Column("credit_amount_kobo", sa.BigInteger(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("provider_tx_ref", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("webhook_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("provider_tx_ref", name="uq_payments_provider_tx_ref"),
        )
        op.create_index("ix_payments_user_id", "payments", ["user_id"])
        op.create_index("ix_payments_provider_tx_ref", "payments", ["provider_tx_ref"])
        op.create_index("ix_payments_status", "payments", ["status"])
        op.create_index("ix_payments_purpose", "payments", ["purpose"])
        return

    if not _has_column(insp, "payments", "purpose"):
        op.add_column("payments", sa.Column("purpose", sa.String(length=50), nullable=True))
        op.create_index("ix_payments_purpose", "payments", ["purpose"])
    if not _has_column(insp, "payments", "credit_amount_kobo"):
        op.add_column("payments", sa.Column("credit_amount_kobo", sa.BigInteger(), nullable=True))
    if not _has_column(insp, "payments", "currency"):
        op.add_column("payments", sa.Column("currency", sa.String(length=10), nullable=True))
    if not _has_column(insp, "payments", "tier"):
        op.add_column("payments", sa.Column("tier", sa.String(length=50), nullable=True))
    # ensure existing metadata column is usable (do not rename/drop)
    if not _has_column(insp, "payments", "metadata") and _has_column(insp, "payments", "payment_metadata"):
        op.alter_column("payments", "payment_metadata", new_column_name="metadata")


def downgrade() -> None:
    # non-destructive downgrade (leave columns to avoid data loss)
    pass
