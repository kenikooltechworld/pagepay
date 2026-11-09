"""Study HTTP routes (thin layer)."""

from fastapi import APIRouter, Depends

from app.controllers.study_controller import StudyController
from app.core.database import get_db
from app.models.user import User
from app.schemas.study import (
    EssaySubmitRequest,
    EssayReviewResponse,
    GenerateAssetRequest,
    GenerateAssetResponse,
    MaterialDetail,
    MaterialSummary,
    MaterialUploadRequest,
)
from app.schemas.study_unlock import UnlockResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/study", tags=["study"])


def get_controller(db=Depends(get_db)) -> StudyController:
    return StudyController(db)


@router.post("/materials", response_model=MaterialSummary, status_code=201)
async def upload_material(
    payload: MaterialUploadRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.upload_material(
        current_user, payload.title, payload.content, payload.exam_type, payload.education_level
    )


@router.get("/materials", response_model=list[MaterialSummary])
async def list_materials(
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.list_materials(current_user)


@router.get("/materials/{material_id}", response_model=MaterialDetail)
async def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.get_material(current_user, material_id)


@router.post("/generate", response_model=GenerateAssetResponse)
async def generate_asset(
    payload: GenerateAssetRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.generate_asset(
        current_user, payload.material_id, payload.asset_type, payload.count, payload.topic, payload.difficulty
    )


@router.post("/assets/{asset_id}/unlock", response_model=UnlockResponse)
async def unlock_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.unlock_asset(current_user, asset_id)


@router.post("/essay/submit", response_model=EssayReviewResponse)
async def submit_essay(
    payload: EssaySubmitRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.submit_essay(current_user, payload.material_id, payload.topic, payload.essay)
