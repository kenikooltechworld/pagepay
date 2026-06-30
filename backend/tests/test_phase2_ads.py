"""Phase 2 ad-infrastructure tests.

Covers the four new surfaces:
  1. /api/v1/config/ads        — dev returns Google test IDs, prod
                                 returns the seeded PagePay IDs
  2. Sponsored-every-4th rotation in build_feed_with_sponsored
  3. /api/v1/ads/impression + /api/v1/ads/reward-claim — the
                                 two-step client-driven credit path
  4. /api/v1/ads/google/callback — AdMob SSV webhook: HMAC
                                 verification, duplicate
                                 transaction_id idempotency, FX
                                 failure path

These tests are written against the same in-memory sqlite stack
the rest of the suite uses. The conftest's `setup_db` autouse
fixture drops + recreates the schema per test, so the seed never
runs in tests (we seed what each test needs explicitly).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import pytest

from app.config import settings
from app.models import AppConfig, User
from app.routers.content import build_feed_with_sponsored
from app.services import ads as ads_service
from app.services import fx as fx_service


# Static FX rate the math tests use. Pinning the rate means a
# $0.001 ad credits exactly 120 points at 1500 NGN/USD, which
# keeps the assertions human-readable.
STATIC_FX_RATE = 1500.0


def _stub_fx(monkeypatch, rate: float = STATIC_FX_RATE) -> None:
    """Patch get_usd_to_ngn with a deterministic rate."""
    fx_service.reset_cache_for_tests()

    async def fake_get_usd_to_ngn():
        return fx_service.FxRate(rate=rate, fetched_at=0.0, source="test")

    monkeypatch.setattr(fx_service, "get_usd_to_ngn", fake_get_usd_to_ngn)


async def _register_and_login(client, email: str) -> dict[str, str]:
    """Register a fresh user and return auth headers."""
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "secure1234",
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_content_row(id_: int, *, sponsored: bool = False) -> "object":
    """Build a lightweight stand-in for a ContentCatalog row.

    We don't need a real DB row to exercise the rotation helper —
    the function only reads attributes, never queries. This
    keeps the test fast and decoupled from the ORM.
    """
    from types import SimpleNamespace
    return SimpleNamespace(
        id=id_,
        title=f"item-{id_}",
        is_sponsored=sponsored,
    )


# ── 1. Sponsored rotation helper ──────────────────────────────────
# The `build_feed_with_sponsored` function is the engine of the
# feed endpoint. These tests pin the contract: sponsored appears
# at positions [interval, 2*interval, ...] in the output, organic
# items are dropped from the tail to keep the length constant,
# and the per-user shuffle is deterministic.

def test_sponsored_every_4th_inserts_at_position_4_8_12():
    organic = [_make_content_row(i) for i in range(1, 13)]  # 12 items
    sponsored = [_make_content_row(100 + i, sponsored=True) for i in range(5)]
    out = build_feed_with_sponsored(organic, sponsored, user_id=42, every=4)
    # 12 organic → 12 - (12//4) = 9 organic + 3 sponsored = 12 total
    assert len(out) == 12
    sponsored_positions = [i for i, item in enumerate(out) if item.is_sponsored]
    assert sponsored_positions == [3, 7, 11]  # 0-indexed → 4th, 8th, 12th
    # All sponsored items in the output came from the input
    assert all(item in sponsored for item in out if item.is_sponsored)


def test_sponsored_rotation_disabled_when_every_zero():
    organic = [_make_content_row(i) for i in range(1, 11)]
    sponsored = [_make_content_row(100 + i, sponsored=True) for i in range(5)]
    out = build_feed_with_sponsored(organic, sponsored, user_id=42, every=0)
    # No rotation → organic list unchanged, no sponsored items injected
    assert out == list(organic)
    assert all(not item.is_sponsored for item in out)


def test_sponsored_rotation_skipped_when_no_inventory():
    organic = [_make_content_row(i) for i in range(1, 11)]
    out = build_feed_with_sponsored(organic, sponsored=[], user_id=42, every=4)
    assert out == list(organic)


def test_sponsored_rotation_per_user_is_deterministic():
    """Same user → same shuffle on every call. The per-user seed
    makes the ad order stable across requests so back-button
    navigation doesn't shuffle the feed under the user.
    """
    organic = [_make_content_row(i) for i in range(1, 11)]
    sponsored = [_make_content_row(100 + i, sponsored=True) for i in range(8)]
    out_a = build_feed_with_sponsored(organic, sponsored, user_id=7, every=4)
    out_b = build_feed_with_sponsored(organic, sponsored, user_id=7, every=4)
    assert [item.id for item in out_a] == [item.id for item in out_b]


def test_sponsored_rotation_per_user_differs_across_users():
    """Two different users with the same inventory see different
    sponsored orderings — the per-user seed gives each user a
    unique shuffle.
    """
    organic = [_make_content_row(i) for i in range(1, 11)]
    sponsored = [_make_content_row(100 + i, sponsored=True) for i in range(8)]
    out_user_a = build_feed_with_sponsored(organic, sponsored, user_id=1, every=4)
    out_user_b = build_feed_with_sponsored(organic, sponsored, user_id=2, every=4)
    # The sponsored item ids will likely differ at the same
    # positions. We assert the shuffles are not identical — exact
    # position depends on the seed and a stable test would
    # require pinning the seed, which we don't want to commit.
    sponsored_ids_a = [item.id for item in out_user_a if item.is_sponsored]
    sponsored_ids_b = [item.id for item in out_user_b if item.is_sponsored]
    assert sponsored_ids_a != sponsored_ids_b


def test_sponsored_rotation_caps_at_max_sponsored():
    """More sponsored inventory than `max_sponsored` → only the
    first N (post-shuffle) appear in the output.
    """
    organic = [_make_content_row(i) for i in range(1, 21)]  # 20 items
    sponsored = [_make_content_row(100 + i, sponsored=True) for i in range(50)]
    out = build_feed_with_sponsored(
        organic, sponsored, user_id=42, every=4, max_sponsored=2
    )
    # 20 organic → 20 - (20//4) = 15 organic + 2 sponsored = 17
    # The cap trims the slot count further: 20 // 4 = 5 slots,
    # but max_sponsored=2 means at most 2 sponsored items.
    sponsored_count = sum(1 for item in out if item.is_sponsored)
    assert sponsored_count <= 2


# ── 2. /api/v1/config/ads — dev vs prod ───────────────────────────
# The dev env returns Google's documented test unit IDs; prod
# returns the values seeded by `app/seed.py`. We seed app_config
# explicitly here (the autouse conftest fixture wipes the DB
# between tests, so the lifespan seed never runs in tests).

@pytest.mark.asyncio
async def test_config_ads_dev_returns_google_test_ids(client, db_session):
    """env=dev returns Google's test unit IDs, not the prod ones."""
    # Seed: no app_config rows needed. The dev override is built
    # into `ads_service._dev_value_for` — it doesn't read from
    # the DB at all.
    r = await client.get("/api/v1/config/ads?env=dev")
    assert r.status_code == 200
    body = r.json()
    # Google's documented Android test unit ID for native advanced:
    assert body["in_feed_android"] == "ca-app-pub-3940256099942544/2247696110"
    # App ID for Android test:
    assert body["android_app_id"] == "ca-app-pub-3940256099942544~3347511713"


@pytest.mark.asyncio
async def test_config_ads_prod_returns_seeded_ids(client, db_session):
    """env=prod reads from app_config and returns the seeded IDs."""
    # Seed the prod row. We use the model's primary key directly
    # so the upsert path in `seed.py` doesn't have to run.
    db_session.add(AppConfig(
        key="admob.in_feed.android",
        value="ca-app-pub-3898064484524772/6538723260",
        environment="prod",
        description="seeded by test",
    ))
    db_session.add(AppConfig(
        key="admob.app_id.android",
        value="ca-app-pub-3898064484524772~6521009021",
        environment="prod",
        description="seeded by test",
    ))
    await db_session.commit()

    r = await client.get("/api/v1/config/ads?env=prod")
    assert r.status_code == 200
    body = r.json()
    assert body["in_feed_android"] == "ca-app-pub-3898064484524772/6538723260"
    assert body["android_app_id"] == "ca-app-pub-3898064484524772~6521009021"
    # A key we didn't seed → empty string. The client treats
    # empty as "slot disabled".
    assert body["interstitial_ios"] == ""


@pytest.mark.asyncio
async def test_config_ads_rejects_invalid_env(client):
    """The endpoint pattern-restricts env to dev|prod."""
    r = await client.get("/api/v1/config/ads?env=staging")
    assert r.status_code == 422


# ── 3. Impression + reward-claim two-step path ────────────────────
# The new client-driven path splits "ad watched" into impression
# (logged at load time) and reward-claim (logged at revenue
# callback time). These tests pin both halves.

@pytest.mark.asyncio
async def test_impression_returns_ad_event_id(client, monkeypatch):
    headers = await _register_and_login(client, "imp@example.com")
    r = await client.post(
        "/api/v1/ads/impression",
        headers=headers,
        json={"ad_type": "rewarded", "provider": "admob", "ad_unit": "pagepay_rewarded"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["ad_event_id"], int)
    assert body["ad_event_id"] > 0


@pytest.mark.asyncio
async def test_reward_claim_credits_and_links_to_impression(client, monkeypatch):
    _stub_fx(monkeypatch)
    headers = await _register_and_login(client, "rc@example.com")

    # Step 1: log the impression
    r = await client.post(
        "/api/v1/ads/impression",
        headers=headers,
        json={"ad_type": "rewarded", "provider": "admob", "ad_unit": "pagepay_rewarded"},
    )
    ad_event_id = r.json()["ad_event_id"]

    # Step 2: SDK reports revenue, client claims
    r = await client.post(
        "/api/v1/ads/reward-claim",
        headers=headers,
        json={
            "ad_event_id": ad_event_id,
            "ad_type": "rewarded",
            "provider": "admob",
            "ad_unit": "pagepay_rewarded",
            "revenue_usd": 0.001,
            "transaction_id": "rc-tx-001",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ad_event_id"] == ad_event_id
    assert body["points_credited"] == 120  # 0.001 × 1500 × 0.80 × 100
    assert body["credit_status"] == "credited"

    # Wallet reflects the credit
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 120


@pytest.mark.asyncio
async def test_reward_claim_without_impression_still_credits(client, monkeypatch):
    """A claim that arrives without a prior /impression call
    still credits the wallet. The audit row just doesn't have
    the load-time link.
    """
    _stub_fx(monkeypatch)
    headers = await _register_and_login(client, "noimp@example.com")

    r = await client.post(
        "/api/v1/ads/reward-claim",
        headers=headers,
        json={
            "ad_event_id": None,
            "ad_type": "rewarded",
            "provider": "admob",
            "ad_unit": "pagepay_rewarded",
            "revenue_usd": 0.001,
            "transaction_id": "noimp-tx-001",
        },
    )
    assert r.status_code == 200
    assert r.json()["points_credited"] == 120
    assert r.json()["credit_status"] == "credited"


@pytest.mark.asyncio
async def test_reward_claim_duplicate_tx_id_is_idempotent(client, monkeypatch):
    _stub_fx(monkeypatch)
    headers = await _register_and_login(client, "dupclaim@example.com")

    payload = {
        "ad_event_id": None,
        "ad_type": "rewarded",
        "provider": "admob",
        "ad_unit": "pagepay_rewarded",
        "revenue_usd": 0.001,
        "transaction_id": "dupclaim-tx-001",
    }

    r1 = await client.post("/api/v1/ads/reward-claim", headers=headers, json=payload)
    r2 = await client.post("/api/v1/ads/reward-claim", headers=headers, json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["points_credited"] == 120
    assert r2.json()["credit_status"] == "duplicate"

    # Single credit
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 120


# ── 4. AdMob SSV webhook ─────────────────────────────────────────
# The HMAC-SHA256 signature must match for the endpoint to credit.
# Bad signature → 401, no credit. Good signature → credit. A
# duplicate transaction_id → 200 with status=duplicate, no
# re-credit. FX failure → 200 with status=fx_unavailable (we
# don't retry-storm the FX endpoint).

_ADMOB_WEBHOOK_SECRET = "test-admob-secret-do-not-use-in-prod"


def _sign_admob_payload(body: bytes) -> str:
    """Sign a raw body with the test webhook secret."""
    return hmac.new(
        _ADMOB_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


def _admob_callback_body(user_id: int, transaction_id: str) -> bytes:
    """Shape AdMob SSV sends (JSON variant)."""
    return json.dumps({
        "transaction_id": transaction_id,
        "ad_unit_id": "pagepay_rewarded",
        "reward_amount": 0.001,
        "custom_data": {"user_id": str(user_id)},
    }).encode("utf-8")


@pytest.mark.asyncio
async def test_admob_ssv_credits_with_valid_signature(client, monkeypatch):
    _stub_fx(monkeypatch)
    settings.admob_webhook_secret = _ADMOB_WEBHOOK_SECRET
    try:
        headers = await _register_and_login(client, "ssv@example.com")
        # Look up the user id from /me
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]

        body = _admob_callback_body(user_id, "ssv-tx-001")
        signature = _sign_admob_payload(body)
        r = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={
                "X-Admob-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200, r.text
        body_json = r.json()
        assert body_json["status"] == "credited"
        assert body_json["points_credited"] == 120

        # Wallet credited
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.json()["points_balance"] == 120
    finally:
        settings.admob_webhook_secret = None


@pytest.mark.asyncio
async def test_admob_ssv_rejects_bad_signature(client, monkeypatch):
    _stub_fx(monkeypatch)
    settings.admob_webhook_secret = _ADMOB_WEBHOOK_SECRET
    try:
        headers = await _register_and_login(client, "badsig@example.com")
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]

        body = _admob_callback_body(user_id, "badsig-tx-001")
        # Sign with a different secret — the signature won't match
        bad_signature = hmac.new(
            b"wrong-secret", body, hashlib.sha256
        ).hexdigest()
        r = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={
                "X-Admob-Signature": bad_signature,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 401

        # No credit
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.json()["points_balance"] == 0
    finally:
        settings.admob_webhook_secret = None


@pytest.mark.asyncio
async def test_admob_ssv_rejects_missing_signature(client, monkeypatch):
    _stub_fx(monkeypatch)
    settings.admob_webhook_secret = _ADMOB_WEBHOOK_SECRET
    try:
        headers = await _register_and_login(client, "nosig@example.com")
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]
        body = _admob_callback_body(user_id, "nosig-tx-001")
        # No X-Admob-Signature header
        r = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 401
    finally:
        settings.admob_webhook_secret = None


@pytest.mark.asyncio
async def test_admob_ssv_duplicate_transaction_id_returns_200_no_credit(client, monkeypatch):
    """AdMob retries on non-2xx, so the duplicate path MUST
    return 200. A 5xx would cause AdMob to retry and double-credit.
    """
    _stub_fx(monkeypatch)
    settings.admob_webhook_secret = _ADMOB_WEBHOOK_SECRET
    try:
        headers = await _register_and_login(client, "ssvdup@example.com")
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]

        body = _admob_callback_body(user_id, "ssvdup-tx-001")
        signature = _sign_admob_payload(body)

        r1 = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={"X-Admob-Signature": signature, "Content-Type": "application/json"},
        )
        r2 = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={"X-Admob-Signature": signature, "Content-Type": "application/json"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["status"] == "credited"
        assert r2.json()["status"] == "duplicate"
        assert r2.json()["points_credited"] == 120  # the original

        # Single credit
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.json()["points_balance"] == 120
    finally:
        settings.admob_webhook_secret = None


@pytest.mark.asyncio
async def test_admob_ssv_returns_200_on_fx_failure(client, monkeypatch):
    """FX outage → 200 with status=fx_unavailable. AdMob would
    otherwise retry-storm us, hammering the broken FX endpoint.
    """
    fx_service.reset_cache_for_tests()

    async def broken_fx():
        raise RuntimeError("FX endpoint down")

    monkeypatch.setattr(fx_service, "get_usd_to_ngn", broken_fx)
    settings.admob_webhook_secret = _ADMOB_WEBHOOK_SECRET
    try:
        headers = await _register_and_login(client, "ssvfx@example.com")
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]

        body = _admob_callback_body(user_id, "ssvfx-tx-001")
        signature = _sign_admob_payload(body)
        r = await client.post(
            "/api/v1/ads/google/callback",
            content=body,
            headers={"X-Admob-Signature": signature, "Content-Type": "application/json"},
        )
        # 200 (not 5xx) — AdMob must not retry on FX failure.
        assert r.status_code == 200
        assert r.json()["status"] == "fx_unavailable"
    finally:
        settings.admob_webhook_secret = None


@pytest.mark.asyncio
async def test_applovin_callback_returns_501(client):
    """AppLovin is stubbed until the integration lands."""
    r = await client.post("/api/v1/ads/applovin/callback", json={})
    assert r.status_code == 501
