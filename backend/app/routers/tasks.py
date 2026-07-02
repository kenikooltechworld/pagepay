"""Phase 7: Social Tasks Marketplace - Worker endpoints."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.database import get_db
from app.models import User, Task, TaskSubmission, UserReputation
from app.schemas import (
    TaskListItem, TaskResponse, TaskSubmitRequest, TaskSubmissionResponse,
    WorkerStatsResponse, LeaderboardResponse, LeaderboardEntry
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger("uvicorn.error")


@router.get("", response_model=list[TaskListItem])
async def list_tasks(
    category: str | None = None,
    platform: str | None = None,
    min_reward: int | None = None,
    max_reward: int | None = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available tasks for worker.
    
    Filters:
    - Only active, not expired tasks
    - User hasn't already completed
    - User meets eligibility (level, approval rate, demographics)
    """
    if limit > 50:
        limit = 50
    offset = (page - 1) * limit
    
    # Build query with filters
    query = select(Task).where(
        Task.status == "active",
        Task.expires_at > datetime.now(timezone.utc),
        Task.completed_count < Task.max_completions,
    )
    
    if category:
        query = query.where(Task.category == category)
    if platform:
        query = query.where(Task.platform == platform)
    if min_reward:
        query = query.where(Task.reward_amount >= min_reward)
    if max_reward:
        query = query.where(Task.reward_amount <= max_reward)
    
    # Check user reputation for eligibility
    rep_result = await db.execute(
        select(UserReputation).where(UserReputation.user_id == current_user.id)
    )
    user_rep = rep_result.scalar_one_or_none()
    
    if user_rep:
        query = query.where(
            Task.min_worker_level <= user_rep.worker_level,
            Task.min_approval_rate <= user_rep.approval_rate
        )
    
    # Exclude tasks user already submitted
    subquery = select(TaskSubmission.task_id).where(
        TaskSubmission.worker_id == current_user.id
    )
    query = query.where(Task.id.not_in(subquery))
    
    # Sorting
    if sort == "highest_reward":
        query = query.order_by(Task.reward_amount.desc())
    elif sort == "quickest":
        query = query.order_by(Task.time_limit_minutes.asc())
    elif sort == "popular":
        query = query.order_by(Task.completed_count.desc())
    else:  # newest
        query = query.order_by(Task.created_at.desc())
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Format response
    response = []
    for task in tasks:
        sponsor = await db.get(User, task.sponsor_id)
        response.append(TaskListItem(
            id=task.id,
            title=task.title,
            task_type=task.task_type,
            platform=task.platform,
            reward_amount=task.reward_amount,
            max_completions=task.max_completions,
            completed_count=task.completed_count,
            expires_at=task.expires_at,
            sponsor_business_name=sponsor.business_name if sponsor else None,
            time_estimate_minutes=task.time_limit_minutes or 5
        ))
    
    return response


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get task detail for worker."""
    task = await db.get(Task, task_id)
    if not task or task.status != "active":
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/start", status_code=201)
async def start_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Worker starts task (begins timer if time limit set)."""
    task = await db.get(Task, task_id)
    if not task or task.status != "active":
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Task expired")
    
    if task.completed_count >= task.max_completions:
        raise HTTPException(status_code=400, detail="Task full")
    
    # Check if already submitted
    existing = await db.execute(
        select(TaskSubmission).where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.worker_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already submitted this task")
    
    # Create submission record with started_at
    submission = TaskSubmission(
        task_id=task_id,
        worker_id=current_user.id,
        proof_type=task.proof_type,
        status="started",
        started_at=datetime.now(timezone.utc)
    )
    db.add(submission)
    
    # Update user reputation stats
    rep = await db.execute(
        select(UserReputation).where(UserReputation.user_id == current_user.id)
    )
    user_rep = rep.scalar_one_or_none()
    if not user_rep:
        user_rep = UserReputation(user_id=current_user.id)
        db.add(user_rep)
    
    user_rep.tasks_started += 1
    
    await db.commit()
    await db.refresh(submission)
    
    expires_at = None
    if task.time_limit_minutes:
        from datetime import timedelta
        expires_at = submission.started_at + timedelta(minutes=task.time_limit_minutes)
    
    return {
        "submission_id": submission.id,
        "started_at": submission.started_at,
        "expires_at": expires_at,
        "instructions": task.instructions,
        "target_url": task.target_url
    }


@router.get("/my-stats", response_model=WorkerStatsResponse)
async def get_worker_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get worker reputation and stats."""
    rep = await db.execute(
        select(UserReputation).where(UserReputation.user_id == current_user.id)
    )
    user_rep = rep.scalar_one_or_none()
    
    if not user_rep:
        user_rep = UserReputation(user_id=current_user.id)
        db.add(user_rep)
        await db.commit()
        await db.refresh(user_rep)
    
    import json
    badges = json.loads(user_rep.badges) if user_rep.badges else []
    
    return WorkerStatsResponse(
        level=user_rep.worker_level,
        xp=user_rep.worker_xp,
        xp_to_next_level=user_rep.worker_xp_to_next_level,
        tasks_completed=user_rep.tasks_completed,
        tasks_approved=user_rep.tasks_approved,
        approval_rate=user_rep.approval_rate,
        total_earnings=user_rep.total_earnings,
        current_streak_days=user_rep.current_streak_days,
        badges=badges
    )


@router.post("/{task_id}/submit", response_model=TaskSubmissionResponse)
async def submit_task(
    task_id: int,
    proof_image_base64: str | None = None,
    proof_url: str | None = None,
    proof_text: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Worker submits task proof.
    
    Accepts base64 encoded image for screenshot proof type.
    """
    task = await db.get(Task, task_id)
    if not task or task.status != "active":
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get started submission
    submission_result = await db.execute(
        select(TaskSubmission).where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.worker_id == current_user.id,
            TaskSubmission.status == "started"
        )
    )
    submission = submission_result.scalar_one_or_none()
    
    if not submission:
        raise HTTPException(status_code=400, detail="Task not started. Call /start first.")
    
    # Upload image to Cloudinary if provided
    proof_image_url = None
    if proof_image_base64 and task.proof_type in ["screenshot", "photo", "video"]:
        from app.services.cloudinary import upload_base64_image
        try:
            public_id = f"user_{current_user.id}_task_{task_id}_{int(datetime.now().timestamp())}"
            upload_result = await upload_base64_image(proof_image_base64, public_id)
            proof_image_url = upload_result["secure_url"]
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")
            raise HTTPException(status_code=500, detail="Image upload failed")
    
    # Calculate completion time
    completion_time = None
    if submission.started_at:
        completion_time = int((datetime.now(timezone.utc) - submission.started_at).total_seconds())
    
    # Update submission
    submission.proof_image_url = proof_image_url
    submission.proof_url = proof_url
    submission.proof_text = proof_text
    submission.status = "validating"  # Will trigger AI verification
    submission.submitted_at = datetime.now(timezone.utc)
    submission.completion_time_seconds = completion_time
    
    # Update reputation
    rep = await db.execute(
        select(UserReputation).where(UserReputation.user_id == current_user.id)
    )
    user_rep = rep.scalar_one_or_none()
    if user_rep:
        user_rep.tasks_completed += 1
    
    await db.commit()
    await db.refresh(submission)
    
    return TaskSubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        worker_id=submission.worker_id,
        proof_type=submission.proof_type,
        proof_image_url=submission.proof_image_url,
        proof_url=submission.proof_url,
        proof_text=submission.proof_text,
        status=submission.status,
        ai_verified=submission.ai_verified,
        ai_confidence=submission.ai_confidence,
        reviewed_at=submission.reviewed_at,
        rejection_reason=submission.rejection_reason,
        reward_paid=submission.reward_paid,
        submitted_at=submission.submitted_at,
        completion_time_seconds=submission.completion_time_seconds
    )


@router.get("/my-submissions", response_model=list[TaskSubmissionResponse])
async def get_my_submissions(
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get worker's submission history."""
    if limit > 50:
        limit = 50
    offset = (page - 1) * limit
    
    query = select(TaskSubmission).where(
        TaskSubmission.worker_id == current_user.id
    )
    
    if status and status != "all":
        query = query.where(TaskSubmission.status == status)
    
    query = query.order_by(TaskSubmission.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    return [
        TaskSubmissionResponse(
            id=s.id,
            task_id=s.task_id,
            worker_id=s.worker_id,
            proof_type=s.proof_type,
            proof_image_url=s.proof_image_url,
            proof_url=s.proof_url,
            proof_text=s.proof_text,
            status=s.status,
            ai_verified=s.ai_verified,
            ai_confidence=s.ai_confidence,
            reviewed_at=s.reviewed_at,
            rejection_reason=s.rejection_reason,
            reward_paid=s.reward_paid,
            submitted_at=s.submitted_at,
            completion_time_seconds=s.completion_time_seconds
        )
        for s in submissions
    ]
