"""Phase 7: Social Tasks Marketplace

Revision ID: 001_phase7_social_tasks
Revises: 
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '001_phase7_social_tasks'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════
    # 1. ADD PHASE 7 COLUMNS TO USERS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.add_column('users', sa.Column('is_worker', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('users', sa.Column('is_sponsor', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('sponsor_wallet_balance', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('sponsor_verified', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('sponsor_kyc_status', sa.String(length=20), nullable=False, server_default='none'))
    op.add_column('users', sa.Column('sponsor_kyc_submitted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('sponsor_kyc_reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('sponsor_kyc_reviewer_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('business_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('business_registration_number', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('sponsor_auto_approve_ai', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('date_of_birth', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('country', sa.String(length=50), nullable=False, server_default='Nigeria'))
    op.add_column('users', sa.Column('languages', sa.Text(), nullable=True))
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. CREATE TASKS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sponsor_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='social_media'),
        sa.Column('target_url', sa.String(length=1000), nullable=True),
        sa.Column('proof_type', sa.String(length=50), nullable=False),
        sa.Column('proof_instructions', sa.Text(), nullable=True),
        sa.Column('reward_amount', sa.BigInteger(), nullable=False),
        sa.Column('max_completions', sa.Integer(), nullable=False),
        sa.Column('completed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approved_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejected_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pending_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_escrowed', sa.BigInteger(), nullable=False),
        sa.Column('platform_fee_percent', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('platform_fee_amount', sa.BigInteger(), nullable=False),
        sa.Column('target_countries', sa.Text(), nullable=True),
        sa.Column('target_cities', sa.Text(), nullable=True),
        sa.Column('target_gender', sa.String(length=20), nullable=True),
        sa.Column('target_age_min', sa.Integer(), nullable=True),
        sa.Column('target_age_max', sa.Integer(), nullable=True),
        sa.Column('target_languages', sa.Text(), nullable=True),
        sa.Column('min_worker_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('min_approval_rate', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('require_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('require_premium', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('visibility', sa.String(length=20), nullable=False, server_default='public'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('featured', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('time_limit_minutes', sa.Integer(), nullable=True),
        sa.Column('ai_verification_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('ai_auto_approve_threshold', sa.BigInteger(), nullable=False, server_default='0.9'),
        sa.Column('manual_review_required', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index(op.f('ix_tasks_sponsor_id'), 'tasks', ['sponsor_id'], unique=False)
    op.create_index(op.f('ix_tasks_task_type'), 'tasks', ['task_type'], unique=False)
    op.create_index(op.f('ix_tasks_platform'), 'tasks', ['platform'], unique=False)
    op.create_index(op.f('ix_tasks_category'), 'tasks', ['category'], unique=False)
    op.create_index(op.f('ix_tasks_completed_count'), 'tasks', ['completed_count'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tasks_expires_at'), 'tasks', ['expires_at'], unique=False)
    op.create_index(op.f('ix_tasks_created_at'), 'tasks', ['created_at'], unique=False)
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. CREATE TASK_SUBMISSIONS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'task_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('worker_id', sa.BigInteger(), nullable=False),
        sa.Column('proof_type', sa.String(length=50), nullable=False),
        sa.Column('proof_url', sa.String(length=1000), nullable=True),
        sa.Column('proof_image_url', sa.String(length=1000), nullable=True),
        sa.Column('proof_text', sa.Text(), nullable=True),
        sa.Column('proof_metadata', sa.Text(), nullable=True),
        sa.Column('proof_image_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('ai_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('ai_confidence', sa.BigInteger(), nullable=True),
        sa.Column('ai_verification_details', sa.Text(), nullable=True),
        sa.Column('ai_verified_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('auto_approved', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('reward_paid', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('fraud_score', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('flagged_for_review', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('duplicate_screenshot_detected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completion_time_seconds', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index(op.f('ix_task_submissions_task_id'), 'task_submissions', ['task_id'], unique=False)
    op.create_index(op.f('ix_task_submissions_worker_id'), 'task_submissions', ['worker_id'], unique=False)
    op.create_index(op.f('ix_task_submissions_proof_image_hash'), 'task_submissions', ['proof_image_hash'], unique=False)
    op.create_index(op.f('ix_task_submissions_status'), 'task_submissions', ['status'], unique=False)
    op.create_index(op.f('ix_task_submissions_created_at'), 'task_submissions', ['created_at'], unique=False)
    op.create_index(op.f('ix_task_submissions_device_fingerprint'), 'task_submissions', ['device_fingerprint'], unique=False)
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. CREATE USER_REPUTATIONS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'user_reputations',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('worker_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('worker_xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('worker_xp_to_next_level', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('tasks_viewed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_started', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_approved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_rejected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_disputed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approval_rate', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('completion_rate', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('avg_completion_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fastest_completion_seconds', sa.Integer(), nullable=True),
        sa.Column('total_earnings', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('quality_score', sa.BigInteger(), nullable=False, server_default='5.0'),
        sa.Column('badges', sa.Text(), nullable=True),
        sa.Column('current_streak_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_task_date', sa.DateTime(), nullable=True),
        sa.Column('sponsor_rating', sa.BigInteger(), nullable=False, server_default='5.0'),
        sa.Column('sponsor_rating_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_posted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_completed_as_sponsor', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_spent', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('submissions_reviewed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('submissions_approved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('submissions_rejected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sponsor_approval_rate', sa.BigInteger(), nullable=False, server_default='100.0'),
        sa.Column('avg_review_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trusted_sponsor', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    op.create_index(op.f('ix_user_reputations_user_id'), 'user_reputations', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_reputations_worker_level'), 'user_reputations', ['worker_level'], unique=False)
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. CREATE SPONSOR_WALLET_TRANSACTIONS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'sponsor_wallet_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sponsor_id', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('balance_before', sa.BigInteger(), nullable=False),
        sa.Column('balance_after', sa.BigInteger(), nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=True),
        sa.Column('submission_id', sa.BigInteger(), nullable=True),
        sa.Column('payment_reference', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('meta_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index(op.f('ix_sponsor_wallet_transactions_sponsor_id'), 'sponsor_wallet_transactions', ['sponsor_id'], unique=False)
    op.create_index(op.f('ix_sponsor_wallet_transactions_type'), 'sponsor_wallet_transactions', ['type'], unique=False)
    op.create_index(op.f('ix_sponsor_wallet_transactions_task_id'), 'sponsor_wallet_transactions', ['task_id'], unique=False)
    op.create_index(op.f('ix_sponsor_wallet_transactions_created_at'), 'sponsor_wallet_transactions', ['created_at'], unique=False)
    
    # ═══════════════════════════════════════════════════════════════════
    # 6. CREATE SPONSOR_KYC TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'sponsor_kyc',
        sa.Column('sponsor_id', sa.BigInteger(), nullable=False),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('business_registration_number', sa.String(length=100), nullable=True),
        sa.Column('business_type', sa.String(length=50), nullable=True),
        sa.Column('business_address', sa.Text(), nullable=True),
        sa.Column('business_website', sa.String(length=500), nullable=True),
        sa.Column('business_social_media', sa.Text(), nullable=True),
        sa.Column('id_document_url', sa.String(length=1000), nullable=True),
        sa.Column('id_document_type', sa.String(length=50), nullable=True),
        sa.Column('id_document_number', sa.String(length=100), nullable=True),
        sa.Column('business_document_url', sa.String(length=1000), nullable=True),
        sa.Column('contact_person_name', sa.String(length=255), nullable=True),
        sa.Column('contact_person_phone', sa.String(length=20), nullable=True),
        sa.Column('contact_person_email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('sponsor_id')
    )
    
    op.create_index(op.f('ix_sponsor_kyc_sponsor_id'), 'sponsor_kyc', ['sponsor_id'], unique=False)


def downgrade() -> None:
    # Drop Phase 7 tables
    op.drop_index(op.f('ix_sponsor_kyc_sponsor_id'), table_name='sponsor_kyc')
    op.drop_table('sponsor_kyc')
    
    op.drop_index(op.f('ix_sponsor_wallet_transactions_created_at'), table_name='sponsor_wallet_transactions')
    op.drop_index(op.f('ix_sponsor_wallet_transactions_task_id'), table_name='sponsor_wallet_transactions')
    op.drop_index(op.f('ix_sponsor_wallet_transactions_type'), table_name='sponsor_wallet_transactions')
    op.drop_index(op.f('ix_sponsor_wallet_transactions_sponsor_id'), table_name='sponsor_wallet_transactions')
    op.drop_table('sponsor_wallet_transactions')
    
    op.drop_index(op.f('ix_user_reputations_worker_level'), table_name='user_reputations')
    op.drop_index(op.f('ix_user_reputations_user_id'), table_name='user_reputations')
    op.drop_table('user_reputations')
    
    op.drop_index(op.f('ix_task_submissions_device_fingerprint'), table_name='task_submissions')
    op.drop_index(op.f('ix_task_submissions_created_at'), table_name='task_submissions')
    op.drop_index(op.f('ix_task_submissions_status'), table_name='task_submissions')
    op.drop_index(op.f('ix_task_submissions_proof_image_hash'), table_name='task_submissions')
    op.drop_index(op.f('ix_task_submissions_worker_id'), table_name='task_submissions')
    op.drop_index(op.f('ix_task_submissions_task_id'), table_name='task_submissions')
    op.drop_table('task_submissions')
    
    op.drop_index(op.f('ix_tasks_created_at'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_expires_at'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_completed_count'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_category'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_platform'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_task_type'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_sponsor_id'), table_name='tasks')
    op.drop_table('tasks')
    
    # Drop Phase 7 columns from users table
    op.drop_column('users', 'languages')
    op.drop_column('users', 'country')
    op.drop_column('users', 'city')
    op.drop_column('users', 'date_of_birth')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'sponsor_auto_approve_ai')
    op.drop_column('users', 'business_registration_number')
    op.drop_column('users', 'business_name')
    op.drop_column('users', 'sponsor_kyc_reviewer_id')
    op.drop_column('users', 'sponsor_kyc_reviewed_at')
    op.drop_column('users', 'sponsor_kyc_submitted_at')
    op.drop_column('users', 'sponsor_kyc_status')
    op.drop_column('users', 'sponsor_verified')
    op.drop_column('users', 'sponsor_wallet_balance')
    op.drop_column('users', 'is_sponsor')
    op.drop_column('users', 'is_worker')
