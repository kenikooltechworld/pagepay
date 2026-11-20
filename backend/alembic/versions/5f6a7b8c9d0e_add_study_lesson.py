"""add study lesson structure and progress

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5f6a7b8c9d0e"
down_revision: Union[str, None] = "4e5f6a7b8c9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols = {c["name"] for c in insp.get_columns("study_materials")} if insp.has_table("study_materials") else set()
    if "lesson_structure" not in cols:
        op.add_column("study_materials", sa.Column("lesson_structure", sa.Text(), nullable=True))
    if "lesson_status" not in cols:
        op.add_column("study_materials", sa.Column("lesson_status", sa.String(length=20), nullable=True))
    if "lesson_error" not in cols:
        op.add_column("study_materials", sa.Column("lesson_error", sa.Text(), nullable=True))

    if not insp.has_table("study_lesson_progress"):
        op.create_table(
            "study_lesson_progress",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("material_id", sa.BigInteger(), nullable=False),
            sa.Column("current_segment", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("segment_states", sa.Text(), nullable=True),
            sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "material_id", name="uq_study_lesson_progress_user_material"),
        )
        op.create_index("ix_study_lesson_progress_user_id", "study_lesson_progress", ["user_id"], unique=False)
        op.create_index("ix_study_lesson_progress_material_id", "study_lesson_progress", ["material_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("study_lesson_progress"):
        op.drop_index("ix_study_lesson_progress_material_id", table_name="study_lesson_progress")
        op.drop_index("ix_study_lesson_progress_user_id", table_name="study_lesson_progress")
        op.drop_table("study_lesson_progress")
    if insp.has_table("study_materials"):
        cols = {c["name"] for c in insp.get_columns("study_materials")}
        for col in ("lesson_error", "lesson_status", "lesson_structure"):
            if col in cols:
                op.drop_column("study_materials", col)
