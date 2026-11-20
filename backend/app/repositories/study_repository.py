"""Data-access layer for study materials and assets."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

import json
from datetime import datetime

from app.models.study import SowUploadJob, StudyAsset, StudyLessonProgress, StudyMaterial


class StudyMaterialRepository:
    """Repository for StudyMaterial persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, material: StudyMaterial) -> StudyMaterial:
        self.db.add(material)
        await self.db.commit()
        await self.db.refresh(material)
        return material

    async def get_by_id(self, material_id: int, user_id: int) -> StudyMaterial | None:
        result = await self.db.execute(
            select(StudyMaterial).where(
                StudyMaterial.id == material_id,
                StudyMaterial.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[StudyMaterial]:
        result = await self.db.execute(
            select(StudyMaterial).where(StudyMaterial.user_id == user_id).order_by(StudyMaterial.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, material: StudyMaterial) -> StudyMaterial:
        await self.db.commit()
        await self.db.refresh(material)
        return material

    async def delete(self, material: StudyMaterial) -> None:
        await self.db.delete(material)


class StudyAssetRepository:
    """Repository for StudyAsset persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, asset: StudyAsset) -> StudyAsset:
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_by_id(self, asset_id: int) -> StudyAsset | None:
        result = await self.db.execute(select(StudyAsset).where(StudyAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def list_for_material(self, material_id: int) -> list[StudyAsset]:
        result = await self.db.execute(
            select(StudyAsset).where(StudyAsset.material_id == material_id).order_by(StudyAsset.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, asset: StudyAsset) -> None:
        await self.db.delete(asset)

    async def update(self, asset: StudyAsset) -> StudyAsset:
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

class SowUploadJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, job: SowUploadJob) -> SowUploadJob:
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get(self, job_id: str) -> SowUploadJob | None:
        result = await self.db.execute(select(SowUploadJob).where(SowUploadJob.id == job_id))
        return result.scalar_one_or_none()

    async def get_for_user(self, job_id: str, user_id: int) -> SowUploadJob | None:
        result = await self.db.execute(
            select(SowUploadJob).where(SowUploadJob.id == job_id, SowUploadJob.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, job_id: str, status: str, *, progress: int | None = None, stage: str | None = None,
        material_id: int | None = None, error_message: str | None = None
    ) -> SowUploadJob | None:
        job = await self.get(job_id)
        if not job:
            return None
        job.status = status
        if progress is not None:
            job.progress = progress
        if stage is not None:
            job.stage = stage
        if material_id is not None:
            job.material_id = material_id
        if error_message is not None:
            job.error_message = error_message
        job.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(job)
        return job


class StudyLessonProgressRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int, material_id: int) -> StudyLessonProgress | None:
        result = await self.db.execute(
            select(StudyLessonProgress).where(
                StudyLessonProgress.user_id == user_id,
                StudyLessonProgress.material_id == material_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int, material_id: int) -> StudyLessonProgress:
        row = await self.get(user_id, material_id)
        if row:
            return row
        row = StudyLessonProgress(
            user_id=user_id,
            material_id=material_id,
            current_segment=0,
            segment_states=json.dumps({}),
            completed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update(
        self, row: StudyLessonProgress, *, current_segment: int | None = None,
        segment_states: dict | None = None, completed: bool | None = None
    ) -> StudyLessonProgress:
        if current_segment is not None:
            row.current_segment = current_segment
        if segment_states is not None:
            row.segment_states = json.dumps(segment_states)
        if completed is not None:
            row.completed = completed
        row.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return row
