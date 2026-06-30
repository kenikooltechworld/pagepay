import pytest
from httpx import AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_content_detail_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/content/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_content_detail_returns_body(client: AsyncClient):
    # Manually create a content row through the same ORM the test app uses.
    from app.models import ContentCatalog
    from tests.conftest import AsyncTestSession

    async with AsyncTestSession() as s:
        s.add(ContentCatalog(
            title="Test Book",
            content_type="book",
            category="fiction",
            source_url="https://example.com/book",
            body_text="Chapter 1. It was a dark and stormy night.",
            author="Tester",
            estimated_read_minutes=5,
        ))
        await s.commit()

    resp = await client.get("/api/v1/content/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test Book"
    assert "stormy night" in (body["body_text"] or "")


@pytest.mark.asyncio
async def test_admin_import_unknown_source(client: AsyncClient):
    resp = await client.post(
        "/api/v1/admin/content/import?source=nope",
        headers={"X-Admin-Token": "dev-admin-token"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_import_requires_token(client: AsyncClient):
    # No header → 401
    r = await client.post("/api/v1/admin/content/import?source=gutenberg")
    assert r.status_code == 401
    # Wrong token → 401
    r = await client.post(
        "/api/v1/admin/content/import?source=gutenberg",
        headers={"X-Admin-Token": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wallet_transactions_empty_for_new_user(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "wallet0@example.com", "password": "secret123"},
    )
    token = reg.json()["access_token"]
    resp = await client.get(
        "/api/v1/wallet/transactions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_wallet_transactions_after_session(client: AsyncClient):
    from app.models import ContentCatalog
    from tests.conftest import AsyncTestSession

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "wallet1@example.com", "password": "secret123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncTestSession() as s:
        s.add(ContentCatalog(
            title="Wallet Book",
            content_type="book",
            category="fiction",
            source_url="https://example.com/wb",
            body_text="Hello world.",
            author="Tester",
            estimated_read_minutes=5,
        ))
        await s.commit()

    create = await client.post(
        "/api/v1/session/start",
        json={"content_id": 1},
        headers=headers,
    )
    assert create.status_code == 201
    sid = create.json()["session_id"]

    await client.post(
        "/api/v1/session/heartbeat",
        json={"session_id": sid, "scroll_events": 5, "app_state": "active"},
        headers=headers,
    )
    end = await client.post(
        "/api/v1/session/end",
        json={"session_id": sid},
        headers=headers,
    )
    assert end.status_code == 200

    resp = await client.get("/api/v1/wallet/transactions", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["description"] == 'Read "Wallet Book"'
    assert rows[0]["points"] == 0  # duration < 10 minutes → no points staged


@pytest.mark.asyncio
async def test_session_end_unverified_returns_zero_points(client: AsyncClient):
    """If scroll_events == 0, the session is unverified and no points are
    awarded — but the row still shows up in wallet transactions as `pending`."""
    from app.models import ContentCatalog
    from tests.conftest import AsyncTestSession

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "unver@example.com", "password": "secret123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncTestSession() as s:
        s.add(ContentCatalog(
            title="Cheat Book",
            content_type="book",
            category="fiction",
            source_url="https://example.com/cheat",
            body_text="",
            author="Tester",
            estimated_read_minutes=5,
        ))
        await s.commit()

    create = await client.post(
        "/api/v1/session/start",
        json={"content_id": 1},
        headers=headers,
    )
    sid = create.json()["session_id"]

    # No heartbeat → 0 scroll events. Session ends unverified.
    end = await client.post(
        "/api/v1/session/end",
        json={"session_id": sid},
        headers=headers,
    )
    assert end.status_code == 200
    body = end.json()
    # Reward gate: nothing pending, nothing to claim.
    assert body["pending_points"] == 0
    assert body["requires_claim"] is False
    assert body["verified"] is False


@pytest.mark.asyncio
async def test_session_end_unknown_id_returns_404(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "noent@example.com", "password": "secret123"},
    )
    token = reg.json()["access_token"]
    resp = await client.post(
        "/api/v1/session/end",
        json={"session_id": 9999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_heartbeat_unknown_id_returns_404(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "noent2@example.com", "password": "secret123"},
    )
    token = reg.json()["access_token"]
    resp = await client.post(
        "/api/v1/session/heartbeat",
        json={"session_id": 9999, "scroll_events": 1, "app_state": "active"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_cannot_be_ended_by_other_user(client: AsyncClient):
    from app.models import ContentCatalog
    from tests.conftest import AsyncTestSession

    # User A creates content
    async with AsyncTestSession() as s:
        s.add(ContentCatalog(
            title="Private Book",
            content_type="book",
            category="fiction",
            source_url="https://example.com/private",
            body_text="",
            author="Tester",
            estimated_read_minutes=5,
        ))
        await s.commit()

    # User A starts a session
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice2@example.com", "password": "secret123"},
    )
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    create = await client.post(
        "/api/v1/session/start",
        json={"content_id": 1},
        headers=headers_a,
    )
    sid = create.json()["session_id"]

    # User B cannot end User A's session
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob2@example.com", "password": "secret123"},
    )
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}
    end = await client.post(
        "/api/v1/session/end",
        json={"session_id": sid},
        headers=headers_b,
    )
    assert end.status_code == 404


# ---------------------------------------------------------------------------
# Reward-gate tests. Phase 1+ no longer credits points directly on /session/end.
# The end endpoint stages `pending_points` and the client must call
# /session/claim after the user watches the post-read ad. These tests pin
# that contract end-to-end.
# ---------------------------------------------------------------------------


async def _register_async(client: AsyncClient, email: str) -> dict:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _make_content(client: AsyncClient, source_url: str = "https://example.com/claim", title: str = "Claim Book") -> None:
    from app.models import ContentCatalog
    from tests.conftest import AsyncTestSession
    async with AsyncTestSession() as s:
        s.add(ContentCatalog(
            title=title,
            content_type="book",
            category="fiction",
            source_url=source_url,
            body_text="Some body.",
            author="Tester",
            estimated_read_minutes=5,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_session_end_stages_pending_and_does_not_credit(client: AsyncClient):
    """End of a verified-but-not-claimed session should set pending_points
    and leave the wallet at 0."""
    await _make_content(client, "https://example.com/claim1", "Pending Book")
    headers = await _register_async(client, "p1@example.com")

    create = await client.post("/api/v1/session/start", json={"content_id": 1}, headers=headers)
    sid = create.json()["session_id"]

    await client.post(
        "/api/v1/session/heartbeat",
        json={"session_id": sid, "scroll_events": 5, "app_state": "active"},
        headers=headers,
    )
    end = await client.post("/api/v1/session/end", json={"session_id": sid}, headers=headers)
    assert end.status_code == 200
    body = end.json()
    # short session → 0 pending, but still verified for the scroll
    assert body["pending_points"] == 0
    assert body["requires_claim"] is False
    assert body["verified"] is True
    assert body["session_id"] == sid

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0


@pytest.mark.asyncio
async def test_claim_credits_pending_points_to_wallet(client: AsyncClient):
    """A verified session that the user then claims should move pending
    points into the wallet."""
    await _make_content(client, "https://example.com/claim2", "Claimable Book")
    headers = await _register_async(client, "c1@example.com")

    # Manually stage a non-zero pending by writing the row directly (we don't
    # want to wait 10 real minutes in a test for the duration floor to trigger).
    from app.models import ReadingSession
    from tests.conftest import AsyncTestSession
    from datetime import datetime, timezone

    create = await client.post("/api/v1/session/start", json={"content_id": 1}, headers=headers)
    sid = create.json()["session_id"]

    async with AsyncTestSession() as s:
        row = (await s.execute(select(ReadingSession).where(ReadingSession.id == sid))).scalar_one()
        row.scroll_events = 5
        row.verified = True
        row.end_time = datetime.now(timezone.utc)
        row.pending_points = 15  # what the duration floor would have produced
        await s.commit()

    # First claim should credit
    claim = await client.post("/api/v1/session/claim", json={"session_id": sid}, headers=headers)
    assert claim.status_code == 200
    body = claim.json()
    assert body["points_earned"] == 15
    assert body["new_balance"] == 15
    assert body["already_claimed"] is False

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 15


@pytest.mark.asyncio
async def test_claim_is_idempotent(client: AsyncClient):
    """Re-claiming the same session must not double-credit the wallet."""
    await _make_content(client, "https://example.com/claim3", "Idempotent Book")
    headers = await _register_async(client, "idem@example.com")

    from app.models import ReadingSession
    from tests.conftest import AsyncTestSession
    from datetime import datetime, timezone

    create = await client.post("/api/v1/session/start", json={"content_id": 1}, headers=headers)
    sid = create.json()["session_id"]

    async with AsyncTestSession() as s:
        row = (await s.execute(select(ReadingSession).where(ReadingSession.id == sid))).scalar_one()
        row.scroll_events = 5
        row.verified = True
        row.end_time = datetime.now(timezone.utc)
        row.pending_points = 10
        await s.commit()

    first = await client.post("/api/v1/session/claim", json={"session_id": sid}, headers=headers)
    assert first.json()["points_earned"] == 10
    assert first.json()["new_balance"] == 10
    assert first.json()["already_claimed"] is False

    # Second claim must return the original grant, not 10 again on top.
    second = await client.post("/api/v1/session/claim", json={"session_id": sid}, headers=headers)
    body = second.json()
    assert body["points_earned"] == 10
    assert body["new_balance"] == 10
    assert body["already_claimed"] is True

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 10


@pytest.mark.asyncio
async def test_claim_without_pending_still_marks_claimed(client: AsyncClient):
    """A session with 0 pending_points should still get `claimed_at` stamped
    so the client can move on without re-trying."""
    from app.models import ReadingSession
    from tests.conftest import AsyncTestSession
    from datetime import datetime, timezone

    headers = await _register_async(client, "zeroclaim@example.com")
    create = await client.post("/api/v1/session/start", json={"content_id": 1}, headers=headers)
    sid = create.json()["session_id"]
    await client.post("/api/v1/session/end", json={"session_id": sid}, headers=headers)

    claim = await client.post("/api/v1/session/claim", json={"session_id": sid}, headers=headers)
    assert claim.status_code == 200
    body = claim.json()
    assert body["points_earned"] == 0
    assert body["already_claimed"] is False

    async with AsyncTestSession() as s:
        row = (await s.execute(select(ReadingSession).where(ReadingSession.id == sid))).scalar_one()
        assert row.claimed_at is not None


@pytest.mark.asyncio
async def test_cannot_claim_someone_elses_session(client: AsyncClient):
    """User B claiming User A's session must 404, not silently grant."""
    from app.models import ReadingSession
    from tests.conftest import AsyncTestSession
    from datetime import datetime, timezone

    headers_a = await _register_async(client, "alicec@example.com")
    create = await client.post("/api/v1/session/start", json={"content_id": 1}, headers=headers_a)
    sid = create.json()["session_id"]
    async with AsyncTestSession() as s:
        row = (await s.execute(select(ReadingSession).where(ReadingSession.id == sid))).scalar_one()
        row.pending_points = 5
        await s.commit()

    headers_b = await _register_async(client, "bobc@example.com")
    resp = await client.post("/api/v1/session/claim", json={"session_id": sid}, headers=headers_b)
    assert resp.status_code == 404