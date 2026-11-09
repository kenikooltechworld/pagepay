"""add wallet ledger and study unlocks

Revision ID: 0a1b2c3d4e5f
Revises: 0565d20229a6
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = "0565d20229a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("wallet_ledger"):
        op.create_table(
            "wallet_ledger",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("direction", sa.String(length=10), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("balance_after", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("reference_type", sa.String(length=50), nullable=True),
            sa.Column("reference_id", sa.String(length=100), nullable=True),
            sa.Column("idempotency_key", sa.String(length=120), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
        op.create_index("ix_wallet_ledger_currency", "wallet_ledger", ["currency"])
        op.create_index("ix_wallet_ledger_source", "wallet_ledger", ["source"])
        op.create_index("ix_wallet_ledger_created_at", "wallet_ledger", ["created_at"])
        op.create_index("ix_wallet_ledger_idempotency_key", "wallet_ledger", ["idempotency_key"], unique=True)

    if not insp.has_table("study_unlocks"):
        op.create_table(
            "study_unlocks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("material_id", sa.BigInteger(), nullable=False),
            sa.Column("points_spent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "asset_id", name="uq_study_unlock_user_asset"),
        )
        op.create_index("ix_study_unlocks_user_id", "study_unlocks", ["user_id"])
        op.create_index("ix_study_unlocks_asset_id", "study_unlocks", ["asset_id"])
        op.create_index("ix_study_unlocks_material_id", "study_unlocks", ["material_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("study_unlocks"):
        op.drop_table("study_unlocks")
    if insp.has_table("wallet_ledger"):
        op.drop_table("wallet_ledger")
