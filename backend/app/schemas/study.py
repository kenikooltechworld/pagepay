"""Pydantic schemas for study endpoints."""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional


class MaterialUploadRequest(BaseModel):
    """POST /study/materials body (text upload)."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, description="Raw study material text")
    exam_type: str | None = Field(default=None, max_length=32)
    education_level: str | None = Field(default=None, max_length=50)


class MaterialUpdateRequest(BaseModel):
    """PATCH /study/materials/{material_id} body."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, min_length=1)
    exam_type: str | None = Field(default=None, max_length=32)
    education_level: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.title is None and self.content is None and self.exam_type is None and self.education_level is None:
            raise ValueError("Provide at least one field to update")
        return self


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
    explanation_structure: dict | None = None
    page_count: int | None = 0
    figure_count: int | None = 0
    has_original_file: bool = False
    file_mime_type: str | None = None
    assets: list[dict] = []
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class GenerateAssetRequest(BaseModel):
    """POST /study/generate body."""

    material_id: int
    asset_type: str = Field(..., pattern="^(mcq|flashcard|essay)$")
    count: int = Field(default=5, ge=1, le=20)
    topic: str | None = Field(default=None, max_length=200)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GenerateAssetResponse(BaseModel):
    """Response from asset generation (locked until SP unlock)."""

    material_id: int
    asset_id: int
    asset_type: str
    topic: str | None = None
    points_to_unlock: int
    unlocked: bool = False
    message: str | None = None


class AssetUpdateRequest(BaseModel):
    """PATCH /study/assets/{asset_id} body."""

    topic: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.topic is None:
            raise ValueError("Provide at least one field to update")
        return self


class EssaySubmitRequest(BaseModel):
    """POST /study/essay/submit body.

    Provide `asset_id` (and optional `question_index`) to review against a specific
    generated essay question from that asset. If omitted, review is generic.
    """

    material_id: int
    topic: str | None = Field(default=None, max_length=200)
    essay: str = Field(..., min_length=10)
    asset_id: int | None = None
    question_index: int = Field(default=0, ge=0)


class EssayReviewResponse(BaseModel):
    """AI review of a submitted essay."""

    correct: bool
    feedback: str
    score: int | None = None
    suggestions: list[str] = []

class SowUploadJobAccepted(BaseModel):
    job_id: str
    status: str = "queued"


class SowUploadJobStatus(BaseModel):
    job_id: str
    status: str
    material_id: int | None = None
    error: str | None = None
    progress: int | None = None
    stage: str | None = None
    updated_at: str | None = None


class SowUploadTextRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=50000)
    exam_type: str | None = Field(default=None, max_length=32)
    education_level: str | None = Field(default=None, max_length=50)