"""Study HTTP routes (thin layer)."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.controllers.study_controller import StudyController
from app.core.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.study import (
    SowUploadJobAccepted,
    SowUploadJobStatus,
    SowUploadTextRequest,
    AssetUpdateRequest,
    EssaySubmitRequest,
    EssayReviewResponse,
    GenerateAssetRequest,
    GenerateAssetResponse,
    MaterialDetail,
    MaterialSummary,
    MaterialUpdateRequest,
    MaterialUploadRequest,
)
from app.schemas.study_unlock import UnlockResponse
from app.services.auth_service import get_current_user
from app.services.study_file_service import extract_text, read_upload

router = APIRouter(prefix="/study", tags=["study"])


def get_controller(db=Depends(get_db)) -> StudyController:
    return StudyController(db)


# --- materials ---


@router.post("/materials", response_model=MaterialSummary, status_code=201)
@limiter.limit("30/hour")
async def upload_material(
    request: Request,
    payload: MaterialUploadRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.upload_material(
        current_user, payload.title, payload.content, payload.exam_type, payload.education_level
    )


@router.post("/materials/upload", response_model=MaterialSummary, status_code=201)
@limiter.limit("20/hour")
async def upload_material_file(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    exam_type: str | None = Form(default=None),
    education_level: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, filename, mime = await read_upload(file)
    extracted_text, page_count = extract_text(data, filename, mime)
    return await controller.upload_material_file(
        current_user, title, exam_type, education_level, data, filename, mime, extracted_text, page_count
    )


@router.get("/materials", response_model=list[MaterialSummary])
@limiter.limit("120/minute")
async def list_materials(
    request: Request,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.list_materials(current_user)


@router.get("/materials/{material_id}", response_model=MaterialDetail)
@limiter.limit("120/minute")
async def get_material(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.get_material(current_user, material_id)


@router.patch("/materials/{material_id}", response_model=MaterialSummary)
@limiter.limit("60/minute")
async def update_material(
    request: Request,
    material_id: int,
    payload: MaterialUpdateRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.update_material(
        current_user, material_id, payload.title, payload.content, payload.exam_type, payload.education_level
    )


@router.delete("/materials/{material_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_material(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    await controller.delete_material(current_user, material_id)
    return None


# --- assets / generation ---


@router.post("/generate", response_model=GenerateAssetResponse)
@limiter.limit("20/hour")
async def generate_asset(
    request: Request,
    payload: GenerateAssetRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.generate_asset(
        current_user, payload.material_id, payload.asset_type, payload.count, payload.topic, payload.difficulty
    )


@router.patch("/assets/{asset_id}")
@limiter.limit("60/minute")
async def update_asset(
    request: Request,
    asset_id: int,
    payload: AssetUpdateRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.update_asset(current_user, asset_id, payload.topic)


@router.delete("/assets/{asset_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_asset(
    request: Request,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    await controller.delete_asset(current_user, asset_id)
    return None


@router.post("/assets/{asset_id}/unlock", response_model=UnlockResponse)
@limiter.limit("60/minute")
async def unlock_asset(
    request: Request,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.unlock_asset(current_user, asset_id)


@router.post("/essay/submit", response_model=EssayReviewResponse)
@limiter.limit("30/hour")
async def submit_essay(
    request: Request,
    payload: EssaySubmitRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.submit_essay(
        current_user, payload.material_id, payload.topic, payload.essay, payload.asset_id, payload.question_index
    )

# --- async SOW jobs ---


@router.post("/sow/upload", response_model=SowUploadJobAccepted, status_code=202)
@limiter.limit("20/hour")
async def sow_upload_text(
    request: Request,
    payload: SowUploadTextRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.create_sow_text_job(current_user, payload.text, payload.exam_type, payload.education_level)


@router.post("/sow/upload-document", response_model=SowUploadJobAccepted, status_code=202)
@limiter.limit("20/hour")
async def sow_upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    exam_type: str | None = Form(default=None),
    education_level: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, filename, mime = await read_upload(file)
    extracted_text, page_count = extract_text(data, filename, mime)
    return await controller.create_sow_file_job(current_user, data, filename, mime, extracted_text, page_count, title, exam_type, education_level)


@router.post("/sow/upload-image", response_model=SowUploadJobAccepted, status_code=202)
@limiter.limit("20/hour")
async def sow_upload_image(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    exam_type: str | None = Form(default=None),
    education_level: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    # For now treat images like files: extract text if possible (e.g. text/*) else store filename note
    data, filename, mime = await read_upload(file)
    try:
        extracted_text, page_count = extract_text(data, filename, mime)
    except Exception:
        extracted_text = f"Image upload: {filename}. (Text extraction unavailable for this image; provide text content or a document for parsing.)"
        page_count = 1
    return await controller.create_sow_file_job(current_user, data, filename, mime, extracted_text, page_count, title, exam_type, education_level)


@router.get("/sow/jobs/{job_id}", response_model=SowUploadJobStatus)
@limiter.limit("120/minute")
async def get_sow_job(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.get_sow_job(current_user, job_id)