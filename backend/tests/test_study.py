"""Phase 3: AI Study Prep endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import StudyMaterial, StudyAsset, StudyTransaction, User
from app.routers.auth import get_current_user


def _auth_header(user_id: int) -> dict[str, str]:
    from app.services.auth import create_access_token
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.mark.asyncio
async def test_upload_sow_text(client: AsyncClient, db_session):
    user = User(email="study@test.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    res = await client.post(
        "/api/v1/study/sow/upload",
        json={"text": "Topic 1: Algebra. Subtopic: Equations."},
        headers=_auth_header(user.id),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["material_id"] > 0
    assert data["title"] == "Untitled Material"

    stored = await db_session.execute(select(StudyMaterial).where(StudyMaterial.user_id == user.id))
    assert stored.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_list_materials_empty(client: AsyncClient, db_session):
    user = User(email="empty@test.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    res = await client.get("/api/v1/study/materials", headers=_auth_header(user.id))
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_unlock_with_points(client: AsyncClient, db_session):
    user = User(email="unlock@test.com", password_hash="hash", points_balance=200)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    material = StudyMaterial(user_id=user.id, title="Math", raw_input="x=1", parsed_structure='{"topics":[]}')
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    asset = StudyAsset(material_id=material.id, asset_type="mcq", content_json='{"questions":[]}', points_to_unlock=50)
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post(
        "/api/v1/study/unlock",
        json={"asset_id": asset.id, "method": "points"},
        headers=_auth_header(user.id),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["unlocked"] is True
    assert data["new_balance"] == 150

    txn = await db_session.execute(select(StudyTransaction).where(StudyTransaction.asset_id == asset.id))
    assert txn.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_unlock_insufficient_points(client: AsyncClient, db_session):
    user = User(email="poor@test.com", password_hash="hash", points_balance=10)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    material = StudyMaterial(user_id=user.id, title="Math", raw_input="x=1", parsed_structure='{"topics":[]}')
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    asset = StudyAsset(material_id=material.id, asset_type="mcq", content_json='{"questions":[]}', points_to_unlock=50)
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post(
        "/api/v1/study/unlock",
        json={"asset_id": asset.id, "method": "points"},
        headers=_auth_header(user.id),
    )
    assert res.status_code == 402


@pytest.mark.asyncio
async def test_unlock_ad_creates_pending_transaction(client: AsyncClient, db_session):
    user = User(email="ad@test.com", password_hash="hash", points_balance=200)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    material = StudyMaterial(user_id=user.id, title="Math", raw_input="x=1", parsed_structure='{"topics":[]}')
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    asset = StudyAsset(material_id=material.id, asset_type="mcq", content_json='{"questions":[]}', points_to_unlock=50)
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post(
        "/api/v1/study/unlock",
        json={"asset_id": asset.id, "method": "ad"},
        headers=_auth_header(user.id),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["unlocked"] is False
    assert data["method"] == "ad"
