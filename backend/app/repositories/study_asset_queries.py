"""Data-access additions for study unlock gating."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study import StudyAsset


async def list_assets_for_material(db: AsyncSession, material_id: int) -> list[StudyAsset]:
    result = await db.execute(
        select(StudyAsset).where(StudyAsset.material_id == material_id).order_by(StudyAsset.id.asc())
    )
    return list(result.scalars().all())
