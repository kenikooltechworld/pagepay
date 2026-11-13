"""Study-related database models."""

import json
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyMaterial(Base):
    """One row per uploaded scheme-of-work or syllabus."""

    __tablename__ = "study_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(500))
    exam_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    education_level: Mapped[str] = mapped_column(String(50), default='primary')
    raw_input: Mapped[str] = mapped_column(Text)
    parsed_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    file_mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    figure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyAsset(Base):
    """One generated asset tied to a StudyMaterial."""

    __tablename__ = "study_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(BigInteger, index=True)
    asset_type: Mapped[str] = mapped_column(String(50))  # mcq|flashcard|essay|diagram|video
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content_json: Mapped[str] = mapped_column(Text)
    points_to_unlock: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SowUploadJob(Base):
    """Tracks async SOW upload/parse jobs."""

    __tablename__ = "sow_upload_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|processing|completed|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)