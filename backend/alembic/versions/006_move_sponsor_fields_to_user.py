"""Move sponsor and profile fields from BillTransaction to User

Revision ID: 006_move_sponsor_fields_to_user
Revises: 005_notification_preferences
Create Date: 2026-07-06 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = '006_move_sponsor_fields_to_user'
down_revision: Union[str, None] = '005_notification_preferences'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to users table
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('email_verification_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('email_verification_expires_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login_ip', sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column('last_login_user_agent', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('device_fingerprint', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_worker', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
        batch_op.add_column(sa.Column('is_sponsor', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('sponsor_wallet_balance', sa.BigInteger(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('sponsor_verified', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('sponsor_kyc_status', sa.String(length=20), nullable=False, server_default='none'))
        batch_op.add_column(sa.Column('sponsor_kyc_submitted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_kyc_reviewed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_kyc_reviewer_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('business_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('business_registration_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('sponsor_auto_approve_ai', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('gender', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('date_of_birth', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('country', sa.String(length=50), nullable=False, server_default='Nigeria'))
        batch_op.add_column(sa.Column('languages', sa.Text(), nullable=True))

    # Migrate data from bill_transactions to users
    # For each user, take the most recent bill_transaction row's values
    connection = op.get_bind()
    connection.execute(text("""
        UPDATE users u
        JOIN (
            SELECT user_id, MAX(created_at) as max_created
            FROM bill_transactions
            GROUP BY user_id
        ) latest ON u.id = latest.user_id
        JOIN bill_transactions bt ON bt.user_id = latest.user_id AND bt.created_at = latest.max_created
        SET
            u.is_worker = COALESCE(bt.is_worker, TRUE),
            u.is_sponsor = COALESCE(bt.is_sponsor, FALSE),
            u.sponsor_wallet_balance = COALESCE(bt.sponsor_wallet_balance, 0),
            u.sponsor_verified = COALESCE(bt.sponsor_verified, FALSE),
            u.sponsor_kyc_status = COALESCE(bt.sponsor_kyc_status, 'none'),
            u.sponsor_kyc_submitted_at = bt.sponsor_kyc_submitted_at,
            u.sponsor_kyc_reviewed_at = bt.sponsor_kyc_reviewed_at,
            u.sponsor_kyc_reviewer_id = bt.sponsor_kyc_reviewer_id,
            u.business_name = bt.business_name,
            u.business_registration_number = bt.business_registration_number,
            u.sponsor_auto_approve_ai = COALESCE(bt.sponsor_auto_approve_ai, FALSE),
            u.gender = bt.gender,
            u.date_of_birth = bt.date_of_birth,
            u.city = bt.city,
            u.country = COALESCE(bt.country, 'Nigeria'),
            u.languages = bt.languages
    """))

    # Drop columns from bill_transactions
    with op.batch_alter_table('bill_transactions') as batch_op:
        batch_op.drop_column('is_worker')
        batch_op.drop_column('is_sponsor')
        batch_op.drop_column('sponsor_wallet_balance')
        batch_op.drop_column('sponsor_verified')
        batch_op.drop_column('sponsor_kyc_status')
        batch_op.drop_column('sponsor_kyc_submitted_at')
        batch_op.drop_column('sponsor_kyc_reviewed_at')
        batch_op.drop_column('sponsor_kyc_reviewer_id')
        batch_op.drop_column('business_name')
        batch_op.drop_column('business_registration_number')
        batch_op.drop_column('sponsor_auto_approve_ai')
        batch_op.drop_column('gender')
        batch_op.drop_column('date_of_birth')
        batch_op.drop_column('city')
        batch_op.drop_column('country')
        batch_op.drop_column('languages')

    # Create indexes for new columns
    op.create_index('ix_users_device_fingerprint', 'users', ['device_fingerprint'])
    op.create_index('ix_users_email_verified', 'users', ['email_verified'])


def downgrade() -> None:
    # Add columns back to bill_transactions
    with op.batch_alter_table('bill_transactions') as batch_op:
        batch_op.add_column(sa.Column('is_worker', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
        batch_op.add_column(sa.Column('is_sponsor', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('sponsor_wallet_balance', sa.BigInteger(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('sponsor_verified', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('sponsor_kyc_status', sa.String(length=20), nullable=False, server_default='none'))
        batch_op.add_column(sa.Column('sponsor_kyc_submitted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_kyc_reviewed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_kyc_reviewer_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('business_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('business_registration_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('sponsor_auto_approve_ai', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        batch_op.add_column(sa.Column('gender', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('date_of_birth', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('country', sa.String(length=50), nullable=False, server_default='Nigeria'))
        batch_op.add_column(sa.Column('languages', sa.Text(), nullable=True))

    # Drop new columns from users
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('failed_login_attempts')
        batch_op.drop_column('locked_until')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('email_verification_token')
        batch_op.drop_column('email_verification_expires_at')
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('last_login_ip')
        batch_op.drop_column('last_login_user_agent')
        batch_op.drop_column('device_fingerprint')
        batch_op.drop_column('is_worker')
        batch_op.drop_column('is_sponsor')
        batch_op.drop_column('sponsor_wallet_balance')
        batch_op.drop_column('sponsor_verified')
        batch_op.drop_column('sponsor_kyc_status')
        batch_op.drop_column('sponsor_kyc_submitted_at')
        batch_op.drop_column('sponsor_kyc_reviewed_at')
        batch_op.drop_column('sponsor_kyc_reviewer_id')
        batch_op.drop_column('business_name')
        batch_op.drop_column('business_registration_number')
        batch_op.drop_column('sponsor_auto_approve_ai')
        batch_op.drop_column('gender')
        batch_op.drop_column('date_of_birth')
        batch_op.drop_column('city')
        batch_op.drop_column('country')
        batch_op.drop_column('languages')

    op.drop_index('ix_users_device_fingerprint', table_name='users')
    op.drop_index('ix_users_email_verified', table_name='users')
