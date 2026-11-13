"""add sow upload jobs

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4e5f6a7b8c9d"
down_revision: Union[str, None] = "3d4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("sow_upload_jobs"):
        return
    op.create_table(
        "sow_upload_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("material_id", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sow_upload_jobs_user_id", "sow_upload_jobs", ["user_id"], unique=False)
    op.create_index("ix_sow_upload_jobs_status", "sow_upload_jobs", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("sow_upload_jobs"):
        op.drop_index("ix_sow_upload_jobs_status", table_name="sow_upload_jobs")
        op.drop_index("ix_sow_upload_jobs_user_id", table_name="sow_upload_jobs")
        op.drop_table("sow_upload_jobs")
