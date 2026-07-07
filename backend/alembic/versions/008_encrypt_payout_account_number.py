"""Change payout_accounts.account_number to Text for encrypted storage

Revision ID: 008_encrypt_payout_account_number
Revises: 007_add_user_audit_logs
Create Date: 2026-07-07 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = '008_encrypt_payout_account_number'
down_revision: Union[str, None] = '007_add_user_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('payout_accounts', 'account_number', existing_type=sa.String(10), type_=sa.Text())


def downgrade() -> None:
    op.alter_column('payout_accounts', 'account_number', existing_type=sa.Text(), type_=sa.String(10))
