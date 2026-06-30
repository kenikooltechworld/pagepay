import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from jose import jwt, JWTError
from app.database import get_db
from app.models import ContentCatalog, ReadingProgress
from app.routers.auth import get_current_user
from app.models import User
from app.schemas import ContentItem, ContentDetail, ContinueReading, BookDetail, SliceSummary, ResumeState
from app.services.content.gutendex import import_gutendex
from app.services.content.slicing import force_reslice_all
from app.config import settings

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger("uvicorn.error")


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of 401 if no token.

    Used by /catalog so anonymous browsers can still see the catalog.
    /progress and /continue stay strictly behind auth.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    user = (await db.execute(select(User).where(User.id == int(user_id)))).scalar_one_or_none()
    return user


@router.get("/catalog", response_model=list[ContentItem])
async def list_catalog(
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    exclude_read: bool = Query(
        False,
        description="If true, omit works the current user has finished reading. Requires auth.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Browse the public catalog.

    Only parent works and standalone slices are returned — child slices
    (parts of a sliced book) are intentionally hidden so the user sees
    each book once and then drills into its slices from the reader.

    `exclude_read=true` requires auth and filters out works the user has
    marked finished. Pass false (default) for an anonymous browser view.
    """
    stmt = select(ContentCatalog).where(ContentCatalog.parent_work_id.is_(None))
    if category:
        stmt = stmt.where(ContentCatalog.category == category)

    if exclude_read:
        if current_user is None:
            # Auth dependency will already 401; belt + suspenders.
            raise HTTPException(status_code=401, detail="Sign in to exclude read works")
        finished_ids_subq = (
            select(ReadingProgress.work_id)
            .where(ReadingProgress.user_id == current_user.id)
            .where(ReadingProgress.is_finished == True)  # noqa: E712
        )
        stmt = stmt.where(ContentCatalog.id.notin_(finished_ids_subq))

    stmt = stmt.order_by(ContentCatalog.id.asc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return [
        ContentItem(
            id=item.id,
            title=item.title,
            content_type=item.content_type,
            category=item.category,
            author=item.author,
            estimated_read_minutes=item.estimated_read_minutes,
            is_sponsored=item.is_sponsored,
        )
        for item in items
    ]


@router.get("/continue", response_model=ContinueReading)
async def continue_reading(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convenience alias for GET /progress/continue.

    Returns the slice the user should read next, or `has_in_progress=false`
    if they have no in-progress work. The client can hit this when
    navigating to the reader or building a "continue" banner on home.
    """
    # Defer to the progress router's logic via a thin lookup.
    rp_row = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .where(ReadingProgress.is_finished == False)  # noqa: E712
        # MySQL doesn't support `NULLS LAST` — emulate with two sort keys.
        # Rows with `last_read_at IS NULL` sort to the end because `1 > 0`,
        # then the secondary `desc()` puts the most recent timestamp first.
        .order_by(ReadingProgress.last_read_at.is_(None).asc(), ReadingProgress.last_read_at.desc())
        .limit(1)
    )
    rp = rp_row.scalar_one_or_none()
    if rp is None:
        return ContinueReading(
            slice_id=None, work_id=None, work_title=None, slice_title=None,
            slice_order=0, total_slices=0, percent_complete=0,
            has_in_progress=False, scroll_offset_px=0,
        )

    slice_id = rp.current_slice_id
    if slice_id is None:
        # No pointer yet — return the first slice's id if it exists.
        from app.models import ContentCatalog as CC
        first = (await db.execute(
            select(CC)
            .where(CC.parent_work_id == rp.work_id)
            .where(CC.read_order == 1)
            .limit(1)
        )).scalar_one_or_none()
        if first is not None:
            slice_id = first.id

    if slice_id is None:
        return ContinueReading(
            slice_id=None, work_id=rp.work_id, work_title=None, slice_title=None,
            slice_order=rp.current_slice_order, total_slices=rp.total_slices,
            percent_complete=0, has_in_progress=True, scroll_offset_px=0,
        )

    from app.models import ContentCatalog as CC, SliceBookmark as SB
    slice_obj = (await db.execute(select(CC).where(CC.id == slice_id))).scalar_one_or_none()
    if slice_obj is None:
        return ContinueReading(
            slice_id=None, work_id=None, work_title=None, slice_title=None,
            slice_order=0, total_slices=0, percent_complete=0,
            has_in_progress=False, scroll_offset_px=0,
        )
    work = (await db.execute(select(CC).where(CC.id == rp.work_id))).scalar_one_or_none()
    bm = (await db.execute(
        select(SB.scroll_offset_px)
        .where(SB.user_id == current_user.id)
        .where(SB.slice_id == slice_id)
        .limit(1)
    )).scalar_one_or_none() or 0

    percent = int((rp.slices_completed / rp.total_slices) * 100) if rp.total_slices > 0 else 0
    return ContinueReading(
        slice_id=slice_id,
        work_id=rp.work_id,
        work_title=work.title if work else None,
        slice_title=slice_obj.title,
        slice_order=rp.current_slice_order,
        total_slices=rp.total_slices,
        percent_complete=min(100, percent),
        has_in_progress=True,
        scroll_offset_px=bm,
    )


@router.get("/{content_id}", response_model=ContentDetail)
async def get_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContentCatalog).where(ContentCatalog.id == content_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentDetail(
        id=item.id,
        title=item.title,
        content_type=item.content_type,
        category=item.category,
        author=item.author,
        body_text=item.body_text,
        estimated_read_minutes=item.estimated_read_minutes,
        is_sponsored=item.is_sponsored,
        parent_work_id=item.parent_work_id,
    )


@router.get("/works/{work_id}", response_model=BookDetail)
async def get_book_detail(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Parent work + the ordered list of its slices.

    Powers the locked-slice detail screen. If the work has no children
    (standalone article, or a book imported before slicing was wired in
    that still hasn't been re-sliced), we surface it as a single-slice
    work so the UI doesn't have to branch on `is_sliced`.

    Anonymous callers can browse — auth is only needed when the client
    wants to overlay the user's per-slice completion state. That's
    intentionally not in this response; clients hit `/progress` separately
    if they need it.
    """
    work_row = await db.execute(
        select(ContentCatalog).where(ContentCatalog.id == work_id)
    )
    work = work_row.scalar_one_or_none()
    if work is None:
        raise HTTPException(status_code=404, detail=f"Work {work_id} not found")

    # Children of this parent.
    children_rows = await db.execute(
        select(ContentCatalog)
        .where(ContentCatalog.parent_work_id == work_id)
        .order_by(ContentCatalog.read_order.asc())
    )
    children = children_rows.scalars().all()

    if children:
        slices = [
            SliceSummary(
                id=child.id,
                title=child.title,
                read_order=child.read_order or idx + 1,
                total_slices=child.total_slices or len(children),
                estimated_read_minutes=child.estimated_read_minutes or 1,
            )
            for idx, child in enumerate(children)
        ]
        is_sliced = True
    else:
        # Standalone — surface the parent itself as a single-slice work so
        # the same UI renders without branching. `total_slices=1` matches
        # how the slicer tags standalone articles.
        slices = [
            SliceSummary(
                id=work.id,
                title=work.title,
                read_order=1,
                total_slices=1,
                estimated_read_minutes=work.estimated_read_minutes or 1,
            )
        ]
        is_sliced = False

    return BookDetail(
        id=work.id,
        title=work.title,
        author=work.author,
        category=work.category,
        estimated_read_minutes=work.estimated_read_minutes or sum(s.estimated_read_minutes for s in slices),
        content_type=work.content_type,
        is_sliced=is_sliced,
        slices=slices,
    )


@router.get("/works/{work_id}/resume", response_model=ResumeState)
async def get_book_resume(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The user's progress against one work. Returns the slice id they
    currently have unlocked plus how many slices they've completed.

    If the user has never touched this work, returns all-zero, is_finished
    false, current_slice_id=None. The detail screen treats "no progress"
    the same as "first slice unlocked" — there's nothing to lock.
    """
    rp_row = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .where(ReadingProgress.work_id == work_id)
    )
    rp = rp_row.scalar_one_or_none()
    if rp is None:
        return ResumeState(
            work_id=work_id,
            current_slice_id=None,
            slices_completed=0,
            total_slices=0,
            percent_complete=0,
            is_finished=False,
        )

    current = rp.current_slice_id
    if current is None and (not rp.is_finished):
        # Pointer was never set — return first slice id if it exists,
        # same fallback the /continue endpoint uses.
        first_row = await db.execute(
            select(ContentCatalog)
            .where(ContentCatalog.parent_work_id == work_id)
            .where(ContentCatalog.read_order == 1)
            .limit(1)
        )
        first = first_row.scalar_one_or_none()
        if first is not None:
            current = first.id

    percent = int(
        (rp.slices_completed / rp.total_slices) * 100
        if rp.total_slices > 0 else 0
    )
    return ResumeState(
        work_id=work_id,
        current_slice_id=current,
        slices_completed=rp.slices_completed,
        total_slices=rp.total_slices,
        percent_complete=min(100, percent),
        is_finished=rp.is_finished,
    )


@router.post("/refresh")
async def refresh_catalog(db: AsyncSession = Depends(get_db)):
    """On-demand catalog refresh — pulls a new page of books from Gutendex,
    then re-slices every parent in the catalog.

    Designed for the empty-state CTA on the catalog tab. Anonymous
    callers can hit it. Behind the SlowAPI limiter (configured per-route
    in `app.limiter`) so a malicious actor can't hammer Gutendex or the
    slice pipeline through us.

    Returns counts the client can show in a toast: how many books were
    imported, how many parents were re-sliced, total child slices added.
    """
    # Pull one fresh page of Gutendex. This will also slice those new
    # parents because gutendex.py is wired to do so.
    imported = await import_gutendex(db, limit=20, start_page=1)
    # Now re-slice the whole catalog so books imported before slicing
    # was wired in (long monoliths with no children) become proper
    # 1-minute slice children too.
    reslice_summary = await force_reslice_all(db)
    return {
        "imported": imported,
        "resliced": reslice_summary,
    }
