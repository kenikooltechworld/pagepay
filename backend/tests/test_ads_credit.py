"""Cover /api/v1/ads/credit.

The endpoint powers "every ad watched = points credited". The math is:
  user_points = int(revenue_usd × fx_rate × 0.80 × 100)

These tests pin the math, the idempotency on transaction_id, the
duplicate-callback path, and the FX-failure-rejection path. They stub
`get_usd_to_ngn` because the production FX endpoint is network-dependent;
the real call path is covered by manual smoke tests against the running
docker stack.
"""

import pytest
from unittest.mock import patch

from app.services import fx as fx_service


# Static FX rate that makes the math easy to assert against.
# At 1500 NGN/USD, a $0.001 ad pays:
#   0.001 × 1500 × 0.80 × 100 = 120 points
STATIC_FX_RATE = 1500.0


def _stub_fx(monkeypatch, rate=STATIC_FX_RATE):
    """Patch get_usd_to_ngn to return a fixed rate so tests are deterministic.

    Also clears the in-process cache so the stub is read on the next call.
    """
    fx_service.reset_cache_for_tests()
    async def fake_get_usd_to_ngn():
        return fx_service.FxRate(rate=rate, fetched_at=0.0, source="test")
    monkeypatch.setattr(fx_service, "get_usd_to_ngn", fake_get_usd_to_ngn)


@pytest.mark.asyncio
async def test_register_login_ads_credit_round_trip(client, monkeypatch):
    """Happy path: register, login, post one ad credit, see wallet bump."""
    _stub_fx(monkeypatch)

    # Register
    r = await client.post("/api/v1/auth/register", json={
        "email": "ads@example.com",
        "password": "secure1234",
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Baseline balance
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["points_balance"] == 0

    # Credit one ad: $0.001 × 1500 NGN/USD × 0.80 × 100 = 120 points
    r = await client.post(
        "/api/v1/ads/credit",
        headers=headers,
        json={
            "ad_unit": "pre_read",
            "provider": "mock",
            "revenue_usd": 0.001,
            "transaction_id": "tx-happy-001",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points_credited"] == 120
    assert body["new_balance"] == 120
    assert body["credit_status"] == "credited"
    assert abs(body["fx_rate_used"] - STATIC_FX_RATE) < 0.01

    # Wallet now reflects the bump
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.json()["points_balance"] == 120


@pytest.mark.asyncio
async def test_duplicate_transaction_id_is_idempotent(client, monkeypatch):
    """Same transaction_id fired twice = one credit. Replay-safe."""
    _stub_fx(monkeypatch)

    r = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "ad_unit": "post_read",
        "provider": "mock",
        "revenue_usd": 0.001,
        "transaction_id": "tx-dup-001",
    }

    r1 = await client.post("/api/v1/ads/credit", headers=headers, json=payload)
    r2 = await client.post("/api/v1/ads/credit", headers=headers, json=payload)

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["points_credited"] == 120
    assert r2.json()["credit_status"] == "duplicate"

    # Balance only went up once
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 120


@pytest.mark.asyncio
async def test_rejected_low_value_does_not_credit(client, monkeypatch):
    """An ad that rounds to 0 points does NOT bump the wallet."""
    _stub_fx(monkeypatch, rate=1500.0)

    r = await client.post("/api/v1/auth/register", json={
        "email": "low@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # $0.0000001 × 1500 × 0.80 × 100 = 0.012 → int(...) = 0
    r = await client.post(
        "/api/v1/ads/credit",
        headers=headers,
        json={
            "ad_unit": "pre_read",
            "provider": "mock",
            "revenue_usd": 0.0000001,
            "transaction_id": "tx-low-001",
        },
    )
    assert r.status_code == 200
    assert r.json()["credit_status"] == "rejected_low_value"
    assert r.json()["points_credited"] == 0

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0


@pytest.mark.asyncio
async def test_fx_failure_rejects_credit(client, monkeypatch):
    """If the FX endpoint fails, we MUST NOT credit at a stale rate."""
    fx_service.reset_cache_for_tests()
    async def broken_fx():
        raise RuntimeError("FX endpoint down")
    monkeypatch.setattr(fx_service, "get_usd_to_ngn", broken_fx)

    r = await client.post("/api/v1/auth/register", json={
        "email": "brokenfx@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/credit",
        headers=headers,
        json={
            "ad_unit": "pre_read",
            "provider": "mock",
            "revenue_usd": 0.001,
            "transaction_id": "tx-broken-fx-001",
        },
    )
    # We return 503 when FX is unavailable so the client can retry.
    assert r.status_code == 503, r.text

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0  # Never credited


@pytest.mark.asyncio
async def test_wallet_credits_accumulate(client, monkeypatch):
    """Multiple distinct ad watches = multiple distinct credits."""
    _stub_fx(monkeypatch)

    r = await client.post("/api/v1/auth/register", json={
        "email": "accum@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(5):
        r = await client.post(
            "/api/v1/ads/credit",
            headers=headers,
            json={
                "ad_unit": "pre_read" if i % 2 == 0 else "post_read",
                "provider": "mock",
                "revenue_usd": 0.001,
                "transaction_id": f"tx-accum-{i:03d}",
            },
        )
        assert r.status_code == 200

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 5 * 120  # 5 × $0.001 ads
