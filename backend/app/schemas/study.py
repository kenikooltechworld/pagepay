"""Pydantic schemas for study endpoints."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class MaterialUploadRequest(BaseModel):
    """POST /study/materials body (text upload)."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, description="Raw study material text")
    exam_type: str | None = Field(default=None, max_length=32)
    education_level: str | None = Field(default=None, max_length=50)


class MaterialSummary(BaseModel):
    """Summary of a study material."""

    id: int
    title: str
    exam_type: str | None = None
    asset_types: list[str] = []
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class MaterialDetail(BaseModel):
    """Detailed study material with parsed structure and asset summaries."""

    id: int
    title: str
    exam_type: str | None = None
    education_level: str | None = None
    content: str | None = None
    parsed_structure: dict | None = None
    assets: list[dict] = []
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class GenerateAssetRequest(BaseModel):
    """POST /study/generate body."""

    material_id: int
    asset_type: str = Field(..., pattern="^(mcq|flashcard|essay)$")
    count: int = Field(default=5, ge=1, le=20)
    topic: str | None = None
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GenerateAssetResponse(BaseModel):
    """Response from asset generation (locked until SP unlock)."""

    material_id: int
    asset_id: int
    asset_type: str
    points_to_unlock: int
    unlocked: bool = False
    message: str | None = None


class EssaySubmitRequest(BaseModel):
    """POST /study/essay/submit body."""

    material_id: int
    topic: str | None = None
    essay: str = Field(..., min_length=10)


class EssayReviewResponse(BaseModel):
    """AI review of a submitted essay."""

    correct: bool
    feedback: str
    score: int | None = None
    suggestions: list[str] = []
