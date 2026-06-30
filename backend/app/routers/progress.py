"""Reading-progress endpoints.

The user opens the app. We tell them where to read next via
GET /api/v1/progress/continue. As they scroll within a slice, the reader
saves scroll position via POST /api/v1/progress/bookmark. When they
finish a slice (or navigate to the next one), POST /api/v1/progress/finish
bumps the pointer to the next slice in the work.

If the user has no in-progress work, `continue` returns
`has_in_progress=False` and the client should show fresh content from the
catalog instead.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models import User, ContentCatalog, ReadingProgress, SliceBookmark
from app.routers.auth import get_current_user
from app.schemas import ContinueReading, WorkProgress, BookmarkSave

router = APIRouter(prefix="/progress", tags=["progress"])
logger = logging.getLogger("uvicorn.error")


@router.get("/continue", response_model=ContinueReading)
async def get_continue_reading(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """What should the user read next?

    Looks up the user's most recently active in-progress work. Returns
    the slice they should resume (or start if they're at slice 1). If
    the user has no in-progress work, returns `has_in_progress=False` so
    the client can show the catalog.
    """
    # Find the user's most recent in-progress work.
    rp_row = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .where(ReadingProgress.is_finished == False)  # noqa: E712
        # MySQL doesn't support `NULLS LAST`. Two keys emulate it: NULLs
        # sort to the bottom (`is_(None)` is `1 > 0`), then we sort the
        # non-NULL timestamps newest-first.
        .order_by(ReadingProgress.last_read_at.is_(None).asc(), ReadingProgress.last_read_at.desc())
        .limit(1)
    )
    rp = rp_row.scalar_one_or_none()

    if rp is None:
        return ContinueReading(
            slice_id=None,
            work_id=None,
            work_title=None,
            slice_title=None,
            slice_order=0,
            total_slices=0,
            percent_complete=0,
            has_in_progress=False,
            scroll_offset_px=0,
        )

    # Look up the current slice (or the first slice if pointer is unset).
    slice_id = rp.current_slice_id
    if slice_id is None:
        # Pointer was never set — point to the first slice of the work.
        first_slice = await db.execute(
            select(ContentCatalog)
            .where(ContentCatalog.parent_work_id == rp.work_id)
            .where(ContentCatalog.read_order == 1)
            .limit(1)
        )
        first = first_slice.scalar_one_or_none()
        if first is None:
            # Work has no slices? Shouldn't happen post-slicing, but be safe.
            raise HTTPException(status_code=500, detail="Work has no slices")
        slice_id = first.id
        await db.execute(
            update(ReadingProgress)
            .where(ReadingProgress.id == rp.id)
            .values(current_slice_id=slice_id, current_slice_order=1)
        )
        await db.commit()

    # Resolve the slice row for title etc.
    slice_row = await db.execute(select(ContentCatalog).where(ContentCatalog.id == slice_id))
    slice_obj = slice_row.scalar_one_or_none()
    if slice_obj is None:
        # Pointer is stale (slice was deleted?). Treat as no progress.
        return ContinueReading(
            slice_id=None, work_id=None, work_title=None, slice_title=None,
            slice_order=0, total_slices=0, percent_complete=0,
            has_in_progress=False, scroll_offset_px=0,
        )

    # Work title is the parent's title (parent_work_id on the slice is the work).
    work_row = await db.execute(select(ContentCatalog).where(ContentCatalog.id == rp.work_id))
    work = work_row.scalar_one_or_none()

    # Look up any saved bookmark within this slice.
    bm_row = await db.execute(
        select(SliceBookmark.scroll_offset_px)
        .where(SliceBookmark.user_id == current_user.id)
        .where(SliceBookmark.slice_id == slice_id)
        .limit(1)
    )
    scroll_offset = bm_row.scalar_one_or_none() or 0

    percent = (
        int((rp.slices_completed / rp.total_slices) * 100) if rp.total_slices > 0 else 0
    )

    return ContinueReading(
        slice_id=slice_id,
        work_id=rp.work_id,
        work_title=work.title if work else None,
        slice_title=slice_obj.title,
        slice_order=rp.current_slice_order,
        total_slices=rp.total_slices,
        percent_complete=min(100, percent),
        has_in_progress=True,
        scroll_offset_px=scroll_offset,
    )


@router.get("", response_model=list[WorkProgress])
async def list_in_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All works the user has started but not finished.

    Powers a "Continue reading" section on the home screen — shows
    every in-progress work as a card, newest first.
    """
    rows = await db.execute(
        select(ReadingProgress, ContentCatalog.title)
        .join(ContentCatalog, ContentCatalog.id == ReadingProgress.work_id)
        .where(ReadingProgress.user_id == current_user.id)
        # MySQL doesn't support `NULLS LAST` — emulate with two keys
        # (see /continue for rationale).
        .order_by(ReadingProgress.last_read_at.is_(None).asc(), ReadingProgress.last_read_at.desc())
    )
    out: list[WorkProgress] = []
    for rp, work_title in rows.all():
        # Slice title: if pointer is set, look up. Otherwise "Part 1".
        slice_title = f"{work_title} — Part {rp.current_slice_order}"
        if rp.current_slice_id:
            sl_row = await db.execute(
                select(ContentCatalog.title).where(ContentCatalog.id == rp.current_slice_id)
            )
            t = sl_row.scalar_one_or_none()
            if t:
                slice_title = t
        percent = (
            int((rp.slices_completed / rp.total_slices) * 100)
            if rp.total_slices > 0 else 0
        )
        out.append(
            WorkProgress(
                work_id=rp.work_id,
                work_title=work_title,
                slice_title=slice_title,
                slice_order=rp.current_slice_order,
                total_slices=rp.total_slices,
                slices_completed=rp.slices_completed,
                percent_complete=min(100, percent),
                is_finished=rp.is_finished,
                last_read_at=rp.last_read_at,
            )
        )
    return out


@router.post("/bookmark")
async def save_bookmark(
    payload: BookmarkSave,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save scroll offset within a slice. Idempotent: latest write wins.

    The reader calls this every ~5s while scrolling. We update in place
    rather than insert a new row — one bookmark per (user, slice).
    """
    existing = await db.execute(
        select(SliceBookmark)
        .where(SliceBookmark.user_id == current_user.id)
        .where(SliceBookmark.slice_id == payload.slice_id)
    )
    bm = existing.scalar_one_or_none()
    if bm is None:
        db.add(
            SliceBookmark(
                user_id=current_user.id,
                slice_id=payload.slice_id,
                scroll_offset_px=payload.scroll_offset_px,
            )
        )
    else:
        bm.scroll_offset_px = payload.scroll_offset_px
        bm.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/finish")
async def finish_slice(
    slice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a slice as completed and advance to the next slice.

    Called when:
      - User taps "Next slice" / "Done" button after finishing one
      - Server detects scroll-bottom reached + dwell time exceeded
        (Phase 1.5 — auto-finish on scroll completion)

    If this was the last slice in the work, marks the work finished.
    """
    # Look up the slice to find its parent work.
    slice_row = await db.execute(select(ContentCatalog).where(ContentCatalog.id == slice_id))
    slice_obj = slice_row.scalar_one_or_none()
    if slice_obj is None:
        raise HTTPException(status_code=404, detail="Slice not found")
    if slice_obj.parent_work_id is None:
        # Standalone slice (not part of a work) — nothing to track.
        return {"ok": True, "is_finished": True, "next_slice_id": None}

    work_id = slice_obj.parent_work_id

    # Get or create progress row for this work.
    rp_row = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .where(ReadingProgress.work_id == work_id)
    )
    rp = rp_row.scalar_one_or_none()

    # Total slices snapshot (set on first finish).
    if rp is None:
        total = await db.execute(
            select(ContentCatalog.id)
            .where(ContentCatalog.parent_work_id == work_id)
        )
        total_count = len(total.scalars().all())
        rp = ReadingProgress(
            user_id=current_user.id,
            work_id=work_id,
            current_slice_order=1,
            slices_completed=0,
            total_slices=total_count,
            is_finished=False,
            last_read_at=datetime.now(timezone.utc),
        )
        db.add(rp)
        await db.flush()

    # Find the next slice by order.
    next_slice_row = await db.execute(
        select(ContentCatalog)
        .where(ContentCatalog.parent_work_id == work_id)
        .where(ContentCatalog.read_order == slice_obj.read_order + 1)
    )
    next_slice = next_slice_row.scalar_one_or_none()

    # Update progress: bump counter, advance pointer, set last_read_at.
    rp.slices_completed = min(rp.total_slices, rp.slices_completed + 1)
    rp.last_read_at = datetime.now(timezone.utc)

    if next_slice is None:
        rp.is_finished = True
        rp.current_slice_id = None
        await db.commit()
        return {"ok": True, "is_finished": True, "next_slice_id": None}

    rp.current_slice_id = next_slice.id
    rp.current_slice_order = next_slice.read_order
    await db.commit()
    return {
        "ok": True,
        "is_finished": False,
        "next_slice_id": next_slice.id,
        "next_slice_title": next_slice.title,
    }


@router.post("/start")
async def start_work(
    work_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Begin tracking a work for the user. No-op if already tracking.

    Idempotent — calling twice is fine. Use this when a user taps
    "Read" on a work from the catalog so we can resume them later.
    """
    work_row = await db.execute(select(ContentCatalog).where(ContentCatalog.id == work_id))
    work = work_row.scalar_one_or_none()
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

    rp_row = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .where(ReadingProgress.work_id == work_id)
    )
    rp = rp_row.scalar_one_or_none()
    if rp is not None:
        return {"ok": True, "already_tracked": True, "work_id": work_id}

    total = await db.execute(
        select(ContentCatalog.id).where(ContentCatalog.parent_work_id == work_id)
    )
    total_count = len(total.scalars().all())

    db.add(
        ReadingProgress(
            user_id=current_user.id,
            work_id=work_id,
            current_slice_id=None,
            current_slice_order=1,
            slices_completed=0,
            total_slices=total_count,
            is_finished=False,
            last_read_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return {"ok": True, "already_tracked": False, "work_id": work_id}
