"""Study HTTP routes (thin layer)."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

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
    LessonCheckRequest,
    LessonCheckResponse,
    LessonProgressUpdate,
    LessonResponse,
    MaterialDetail,
    MaterialSummary,
    MaterialUpdateRequest,
    MaterialUploadRequest,
)
from app.schemas.study_unlock import UnlockResponse
from app.services.auth_service import get_current_user
from app.services.study_file_service import (
    extract_pdf_figures,
    extract_text,
    get_pdf_page_count,
    images_to_pdf,
    read_upload,
    render_image_page,
    render_pdf_pages,
)

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


@router.get("/materials/{material_id}/original-file")
@limiter.limit("60/minute")
async def get_material_original_file(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, mime = await controller.get_material_original_file(current_user, material_id)
    extension = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime or "", ".bin")
    return Response(
        content=data,
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="study-material-{material_id}{extension}"'},
    )


@router.get("/materials/{material_id}/page-images")
@limiter.limit("30/minute")
async def get_material_page_images(
    request: Request,
    material_id: int,
    start_page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, mime = await controller.get_material_original_file(current_user, material_id)
    if mime == "application/pdf":
        total = get_pdf_page_count(data)
        page_numbers = list(range(start_page, min(start_page + limit, total + 1)))
        return {"pages": render_pdf_pages(data, page_numbers), "total": total}
    if mime and mime.startswith("image/"):
        pages = render_image_page(data, mime) if start_page == 1 else []
        return {"pages": pages, "total": 1}
    return {"pages": [], "total": 0}


@router.get("/materials/{material_id}/figures")
@limiter.limit("30/minute")
async def get_material_figures(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, mime = await controller.get_material_original_file(current_user, material_id)
    if mime == "application/pdf":
        return extract_pdf_figures(data)
    if mime and mime.startswith("image/"):
        pages = render_image_page(data, mime)
        return [
            {
                "figure_index": 0,
                "page": 1,
                "image_url": pages[0]["image_url"],
                "width": pages[0]["width"],
                "height": pages[0]["height"],
                "description": None,
                "caption": None,
            }
        ]
    return []


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
    selected_pages: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    data, filename, mime = await read_upload(file)
    selected_page_numbers = None
    if selected_pages is not None:
        try:
            page_values = json.loads(selected_pages)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Selected pages must be a JSON array")
        if not isinstance(page_values, list) or not page_values or any(type(page) is not int for page in page_values):
            raise HTTPException(status_code=400, detail="Select at least one valid PDF page")
        if Path(filename).suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Page selection is only supported for PDFs")
        total_pages = get_pdf_page_count(data)
        if len(set(page_values)) != len(page_values):
            raise HTTPException(status_code=400, detail="PDF page selection contains duplicates")
        if any(page < 1 or page > total_pages for page in page_values):
            raise HTTPException(status_code=400, detail="Selected page is outside the document")
        selected_page_numbers = sorted(page_values)
    elif Path(filename).suffix.lower() == ".pdf":
        get_pdf_page_count(data)
    return await controller.create_sow_file_job(
        current_user,
        data,
        filename,
        mime,
        title,
        exam_type,
        education_level,
        selected_page_numbers,
    )


@router.post("/sow/preview-pdf")
@limiter.limit("20/hour")
async def preview_sow_pdf(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    data, filename, _ = await read_upload(file)
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF to preview its pages")
    total_pages = get_pdf_page_count(data)
    pages = render_pdf_pages(data, max_dimension=320)
    preview_pages = [
        {
            "page": page["page"],
            "image_base64": page["image_url"].split(",", 1)[1],
            "width": page["width"],
            "height": page["height"],
            "is_scan": page["is_scan"],
        }
        for page in pages
    ]
    return {"total": total_pages, "pages": preview_pages}


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
    return await _queue_image_uploads(
        [file], current_user, controller, title, exam_type, education_level
    )


@router.post("/sow/upload-images", response_model=SowUploadJobAccepted, status_code=202)
@limiter.limit("20/hour")
async def sow_upload_images(
    request: Request,
    files: list[UploadFile] = File(...),
    title: str | None = Form(default=None),
    exam_type: str | None = Form(default=None),
    education_level: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await _queue_image_uploads(
        files, current_user, controller, title, exam_type, education_level
    )


async def _queue_image_uploads(
    files: list[UploadFile],
    current_user: User,
    controller: StudyController,
    title: str | None,
    exam_type: str | None,
    education_level: str | None,
):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    max_image_bytes = 5 * 1024 * 1024
    max_total_bytes = 25 * 1024 * 1024
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one image")
    if len(files) > 10:
        raise HTTPException(status_code=413, detail="Select no more than 10 images")

    image_data = []
    total_bytes = 0
    for index, file in enumerate(files, start=1):
        mime = (file.content_type or "").lower().split(";", 1)[0].strip()
        if mime not in allowed_types:
            raise HTTPException(
                status_code=415,
                detail=f"Image {index}: use JPEG, PNG, or WebP",
            )
        data = await file.read(max_image_bytes + 1)
        if not data:
            raise HTTPException(status_code=400, detail=f"Image {index} is empty")
        if len(data) > max_image_bytes:
            raise HTTPException(status_code=413, detail=f"Image {index} exceeds the 5 MB limit")
        total_bytes += len(data)
        if total_bytes > max_total_bytes:
            raise HTTPException(status_code=413, detail="Combined images exceed the 25 MB limit")
        raw_name = Path(file.filename or f"page-{index}").name
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name)[:100] or f"page-{index}"
        image_data.append((data, safe_name, mime))
    return await controller.create_sow_image_job(
        current_user,
        image_data,
        images_to_pdf([(data, mime) for data, _, mime in image_data]),
        title,
        exam_type,
        education_level,
    )


@router.get("/sow/jobs/{job_id}", response_model=SowUploadJobStatus)
@limiter.limit("120/minute")
async def get_sow_job(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.get_sow_job(current_user, job_id)


# --- interactive lesson ---


@router.get("/materials/{material_id}/lesson", response_model=LessonResponse)
@limiter.limit("120/minute")
async def get_lesson(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.get_lesson(current_user, material_id)


@router.post("/materials/{material_id}/lesson/generate", response_model=LessonResponse)
@limiter.limit("10/hour")
async def generate_lesson(
    request: Request,
    material_id: int,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.generate_lesson_endpoint(current_user, material_id)


@router.post("/materials/{material_id}/lesson/progress", response_model=LessonResponse)
@limiter.limit("120/minute")
async def update_lesson_progress(
    request: Request,
    material_id: int,
    payload: LessonProgressUpdate,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.update_lesson_progress(
        current_user, material_id, payload.current_segment, payload.segment_states, payload.completed
    )


@router.post("/materials/{material_id}/lesson/check", response_model=LessonCheckResponse)
@limiter.limit("60/hour")
async def check_lesson_answer(
    request: Request,
    material_id: int,
    payload: LessonCheckRequest,
    current_user: User = Depends(get_current_user),
    controller: StudyController = Depends(get_controller),
):
    return await controller.check_lesson_answer(
        current_user, material_id, payload.segment_index, payload.item_type, payload.answer
    )

