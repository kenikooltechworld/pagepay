"""Add referral daily cap columns to users

Revision ID: 002_referral_daily_caps
Revises: 001_phase7_social_tasks
Create Date: 2026-07-01 21:10:00.000000

Adds two columns to the `users` table that the daily-referral-cap
feature (Phase 5 — `app.routers.referral`, `app.services.cron`) writes
to but which were never migrated to MySQL. Without this migration the
API works because referral.py lazily initializes the column, but the
cron's daily reset crashes with:
    pymysql.err.OperationalError (1054, "Unknown column
    'users.referrals_today_reset_at' in 'where clause'")

Schema matches `app.models.User`:
    referrals_today_count    Integer  NOT NULL  default 0
    referrals_today_reset_at DateTime nullable
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_referral_daily_caps'
down_revision: Union[str, None] = '001_phase7_social_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'referrals_today_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'referrals_today_reset_at',
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'referrals_today_reset_at')
    op.drop_column('users', 'referrals_today_count')
