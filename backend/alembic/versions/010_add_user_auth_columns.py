"""Add missing user auth columns to production users table.

Revision ID: 010_add_user_auth_columns
Revises: 009_adjust_points_conversion_rate
Create Date: 2026-07-08 18:01:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = '010_add_user_auth_columns'
down_revision: Union[str, None] = '009_adjust_points_conversion_rate'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS locked_until DATETIME NULL,
        ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255) NULL,
        ADD COLUMN IF NOT EXISTS email_verification_expires_at DATETIME NULL,
        ADD COLUMN IF NOT EXISTS last_login_at DATETIME NULL,
        ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(45) NULL,
        ADD COLUMN IF NOT EXISTS last_login_user_agent VARCHAR(255) NULL,
        ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(255) NULL,
        ADD COLUMN IF NOT EXISTS sponsor_kyc_status VARCHAR(20) DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS sponsor_kyc_submitted_at DATETIME NULL,
        ADD COLUMN IF NOT EXISTS sponsor_kyc_reviewed_at DATETIME NULL,
        ADD COLUMN IF NOT EXISTS sponsor_kyc_reviewer_id BIGINT NULL,
        ADD COLUMN IF NOT EXISTS business_name VARCHAR(255) NULL,
        ADD COLUMN IF NOT EXISTS business_registration_number VARCHAR(100) NULL,
        ADD COLUMN IF NOT EXISTS sponsor_auto_approve_ai BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS gender VARCHAR(20) NULL,
        ADD COLUMN IF NOT EXISTS date_of_birth DATETIME NULL,
        ADD COLUMN IF NOT EXISTS city VARCHAR(100) NULL,
        ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT 'Nigeria',
        ADD COLUMN IF NOT EXISTS languages TEXT NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS failed_login_attempts,
        DROP COLUMN IF EXISTS locked_until,
        DROP COLUMN IF EXISTS email_verified,
        DROP COLUMN IF EXISTS email_verification_token,
        DROP COLUMN IF EXISTS email_verification_expires_at,
        DROP COLUMN IF EXISTS last_login_at,
        DROP COLUMN IF EXISTS last_login_ip,
        DROP COLUMN IF EXISTS last_login_user_agent,
        DROP COLUMN IF EXISTS device_fingerprint,
        DROP COLUMN IF EXISTS sponsor_kyc_status,
        DROP COLUMN IF EXISTS sponsor_kyc_submitted_at,
        DROP COLUMN IF EXISTS sponsor_kyc_reviewed_at,
        DROP COLUMN IF EXISTS sponsor_kyc_reviewer_id,
        DROP COLUMN IF EXISTS business_name,
        DROP COLUMN IF EXISTS business_registration_number,
        DROP COLUMN IF EXISTS sponsor_auto_approve_ai,
        DROP COLUMN IF EXISTS gender,
        DROP COLUMN IF EXISTS date_of_birth,
        DROP COLUMN IF EXISTS city,
        DROP COLUMN IF EXISTS country,
        DROP COLUMN IF EXISTS languages
    """)
