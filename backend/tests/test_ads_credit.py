"""Cover the SSV-only ad credit flow.

The legacy /api/v1/ads/credit, /api/v1/ads/impression, and
/api/v1/ads/reward-claim endpoints are now 410 Gone — they accepted
a client-supplied `revenue_usd` and were an obvious attack surface.
The replacement flow is server-authoritative:

  1. Client: POST /api/v1/ads/request-token → get `custom_data`
  2. Client: passes custom_data to AdMob
  3. AdMob: fires SSV callback (server-side, ECDSA-signed)
  4. Server: SSV handler verifies, looks up AdRequest, credits

The tests below pin the parts we can exercise in-process:

  - /ads/request-token issues a token and binds it to a user + unit
  - /ads/request-token rejects non-rewarded_* units upfront (400)
  - SSV handler rejects forged signatures (401)
  - SSV handler credits the user when a valid AdRequest exists
  - /ads/recent-credits returns the credited AdEvent rows
  - /ads/credit is 410 Gone
  - /ads/reward-claim is 410 Gone

The actual ECDSA P-256 verification against Google's published keys
is mocked here (it requires network) — the unit-level signature
plumbing is covered by a separate test that fakes a known
key_id→key pair.
"""

import base64
import json
import time
from unittest.mock import patch
from urllib.parse import urlencode

import pytest

from app.services import ads as ads_service


def _user_id_from_jwt(jwt_token: str) -> int:
    """Decode the access_token JWT to read its `sub` claim (the user id).

    The /api/v1/auth/register endpoint only returns `access_token` +
    `token_type` — not the full user object — so tests that need the
    user id have to crack the token open. JWTs are signed but not
    encrypted, so base64-decoding the payload is enough.
    """
    parts = jwt_token.split(".")
    assert len(parts) == 3, f"expected 3-part JWT, got {len(parts)}"
    payload_b64 = parts[1]
    # JWTs use URL-safe base64 without padding
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    return int(json.loads(decoded)["sub"])


# ── /ads/request-token ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_token_issues_token_for_rewarded_unit(client):
    """POST /ads/request-token with a rewarded_android unit returns
    a token + custom_data bound to the user."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "rt1@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/request-token",
        headers=headers,
        json={"ad_unit": "rewarded_android"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"]
    assert body["ad_unit"] == "rewarded_android"
    # custom_data is "user_id:token" — the only state carried into
    # the SDK. The server reads it back from the SSV callback.
    assert body["custom_data"].endswith(f":{body['token']}")


@pytest.mark.asyncio
async def test_request_token_rejects_non_rewarded_unit(client):
    """A non-rewarded_* unit (in_feed, interstitial) earns zero.
    The /request-token endpoint rejects them upfront so the client
    gets a clear 400 instead of a token that will never be honored."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "rt2@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for bad_unit in ("in_feed_android", "interstitial_android", "banner_ios", "foo"):
        r = await client.post(
            "/api/v1/ads/request-token",
            headers=headers,
            json={"ad_unit": bad_unit},
        )
        assert r.status_code == 400, f"unit={bad_unit} should 400, got {r.status_code}"
        assert "rewarded_" in r.json()["detail"]


@pytest.mark.asyncio
async def test_request_token_requires_auth(client):
    """Unauthenticated requests get 401."""
    r = await client.post(
        "/api/v1/ads/request-token",
        json={"ad_unit": "rewarded_android"},
    )
    assert r.status_code == 401


# ── SSV callback ────────────────────────────────────────────────────


def _fake_signer():
    """Return a callable that signs a query string with a test ECDSA key.

    The real AdMob signs with a key from `verifier-keys.json`. The
    SSV handler fetches those keys at runtime, so we monkey-patch
    `_fetch_verifier_keys` to return a single key we control.

    The signing string is the URL-encoded query string with the
    `signature` and `key_id` entries excluded, sorted alphabetically
    by key, formatted as "k=v\\n" joined with a trailing "\\n". This
    matches `routers/ads.py:_verify_admob_ssv_signature`.

    `sign_raw(values)` takes the URL-encoded values (the form that
    appears in the raw query string on the wire) — the caller is
    responsible for URL-encoding first.
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def sign_raw(urlencoded_values: list[tuple[str, str]]) -> str:
        """Sign the URL-encoded query values, excluding signature/key_id.

        `urlencoded_values` is the result of `urlencode(..., doseq=True)`
        on the raw params — so `+` has been escaped to `%2B` and `/` to
        `%2F`. The handler signs over this form.
        """
        excluded = {"signature", "key_id"}
        entries = [(k, v) for k, v in urlencoded_values if k not in excluded]
        entries.sort(key=lambda x: x[0])
        signing_string = "\n".join(f"{k}={v}" for k, v in entries) + "\n"
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
        sig = key.sign(signing_string.encode("utf-8"), _ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(sig).decode("ascii")

    return sign_raw, pub_pem.decode("ascii")


def _build_ssv_qs(params: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str]:
    """URL-encode a list of (key, raw_value) pairs into a query string.

    Returns the URL-encoded (key, value) list SORTED ALPHABETICALLY BY
    KEY (matching the handler's reconstruction in
    `_verify_admob_ssv_signature`) and the final query string. The
    signer signs the sorted form, which is what the handler sees.

    Returns: (sorted_urlencoded_entries, qs_string)
    """
    # urlencode URL-encodes special chars but keeps `=` and `&` as
    # param separators — perfect for our purpose.
    encoded = urlencode(params, doseq=False)
    # Re-parse into a (key, value) list, then SORT BY KEY so the
    # signing string matches what the handler reconstructs from the
    # raw query string.
    entries: list[tuple[str, str]] = []
    for part in encoded.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            entries.append((k, v))
    entries.sort(key=lambda x: x[0])
    return entries, encoded


@pytest.mark.asyncio
async def test_ssv_credits_user_for_valid_request(client, monkeypatch):
    """The full happy path: client requests a token, AdMob signs a
    callback with that token in custom_data, the SSV handler credits
    the user."""
    sign, pub_pem = _fake_signer()
    fake_keys = {"1234": pub_pem}

    async def fake_fetch_keys():
        return fake_keys

    monkeypatch.setattr(
        "app.routers.ads._fetch_verifier_keys", fake_fetch_keys
    )

    # 1. Register + request a token
    r = await client.post("/api/v1/auth/register", json={
        "email": "ssv1@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    user_id = _user_id_from_jwt(token)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/request-token",
        headers=headers,
        json={"ad_unit": "rewarded_android"},
    )
    assert r.status_code == 201
    rt = r.json()
    custom_data = rt["custom_data"]

    # 2. Simulate the AdMob SSV callback. The query string must be
    # URL-encoded (urllib.parse.urlencode) so `+` from base64 output
    # and `/` from the ad_unit ID survive the round trip through
    # request.url.query. The signing string is built from the same
    # URL-encoded values the handler reconstructs.
    callback_params = [
        ("ad_network", "admob"),
        ("ad_unit", "ca-app-pub-3940256099942544/5224354917"),
        ("reward_amount", "9"),
        ("reward_item", "points"),
        ("user_id", str(user_id)),
        ("transaction_id", "ssv-tx-001"),
        ("custom_data", custom_data),
        ("key_id", "1234"),
    ]
    encoded_entries, _ = _build_ssv_qs(callback_params)
    sig = sign(encoded_entries)
    from urllib.parse import quote_plus
    qs = urlencode(callback_params) + f"&signature={quote_plus(sig)}"
    r = await client.get(f"/api/v1/ads/google/callback?{qs}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "credited"
    # Default payout: 10 × USER_SHARE (0.95) = 9 points, floored.
    assert body["points_credited"] == 9

    # 3. Wallet reflects the bump
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 9


@pytest.mark.asyncio
async def test_ssv_rejects_bad_signature(client):
    """A callback with a tampered signature must NOT credit anything.
    The handler returns 401 — no points credited, no AdEvent row."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "ssv2@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Forge a callback with a random base64 signature
    r = await client.get(
        "/api/v1/ads/google/callback"
        "?ad_network=admob&ad_unit=x&reward_amount=9"
        "&user_id=1&transaction_id=forged&custom_data=1:nope"
        "&signature=AAAA&key_id=1234"
    )
    assert r.status_code == 401

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0


@pytest.mark.asyncio
async def test_ssv_unknown_token_is_ignored(client, monkeypatch):
    """A callback that names a token we never issued is ignored
    (200 with reason), not credited. The user_id is validated
    AFTER the token lookup, so a guessed user_id doesn't help."""
    sign, pub_pem = _fake_signer()

    async def fake_fetch_keys():
        return {"1234": pub_pem}

    monkeypatch.setattr(
        "app.routers.ads._fetch_verifier_keys", fake_fetch_keys
    )

    r = await client.post("/api/v1/auth/register", json={
        "email": "ssv3@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    callback_params = [
        ("ad_network", "admob"),
        ("ad_unit", "ca-app-pub-xxx/yyy"),
        ("reward_amount", "9"),
        ("reward_item", "points"),
        ("user_id", "999999"),
        ("transaction_id", "tx-unknown-token"),
        ("custom_data", "999999:does-not-exist"),
        ("key_id", "1234"),
    ]
    encoded_entries, _ = _build_ssv_qs(callback_params)
    sig = sign(encoded_entries)
    # `quote_plus` URL-encodes `+` (which appears in base64 output) to
    # `%2B` so it survives the round trip through `request.url.query`.
    # Without this, httpx decodes `+` to a space, corrupting the
    # signature bytes.
    from urllib.parse import quote_plus
    qs = urlencode(callback_params) + f"&signature={quote_plus(sig)}"
    r = await client.get(f"/api/v1/ads/google/callback?{qs}")
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    assert r.json()["reason"] == "unknown_token"

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0


@pytest.mark.asyncio
async def test_ssv_user_mismatch_is_ignored(client, monkeypatch):
    """A forged callback that uses a real token but the wrong user_id
    is rejected at the user_mismatch step. The signature check
    passes because the body is signed as-is, but the user_id in
    custom_data is bound to the AdRequest row at issuance time."""
    sign, pub_pem = _fake_signer()

    async def fake_fetch_keys():
        return {"1234": pub_pem}

    monkeypatch.setattr(
        "app.routers.ads._fetch_verifier_keys", fake_fetch_keys
    )

    r = await client.post("/api/v1/auth/register", json={
        "email": "ssv4@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    user_id = _user_id_from_jwt(token)
    headers = {"Authorization": f"Bearer {token}"}

    # Request a token for the real user
    r = await client.post(
        "/api/v1/ads/request-token",
        headers=headers,
        json={"ad_unit": "rewarded_android"},
    )
    real_custom_data = r.json()["custom_data"]

    # Forge a callback claiming custom_data = "999999:real_token"
    # (a user_id that does NOT match the real user's id). We pick
    # 999999 specifically because SQLite auto-increment starts at 1
    # so the first registered user in a test is almost certainly
    # user_id=1 — using 999999 guarantees a mismatch.
    real_token = real_custom_data.split(":", 1)[1]
    callback_params = [
        ("ad_network", "admob"),
        ("ad_unit", "ca-app-pub-xxx/yyy"),
        ("reward_amount", "9"),
        ("reward_item", "points"),
        ("user_id", "999999"),
        ("transaction_id", "tx-mismatch"),
        ("custom_data", f"999999:{real_token}"),
        ("key_id", "1234"),
    ]
    encoded_entries, _ = _build_ssv_qs(callback_params)
    sig = sign(encoded_entries)
    # `quote_plus` URL-encodes `+` (which appears in base64 output) to
    # `%2B` so it survives the round trip through `request.url.query`.
    # Without this, httpx decodes `+` to a space, corrupting the
    # signature bytes.
    from urllib.parse import quote_plus
    qs = urlencode(callback_params) + f"&signature={quote_plus(sig)}"
    r = await client.get(f"/api/v1/ads/google/callback?{qs}")
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    assert r.json()["reason"] == "user_mismatch"

    # The real user's wallet is unaffected
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["points_balance"] == 0


# ── /ads/recent-credits ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_credits_returns_credited_events(client, monkeypatch):
    """After an SSV credit, the event shows up in /recent-credits."""
    sign, pub_pem = _fake_signer()

    async def fake_fetch_keys():
        return {"1234": pub_pem}

    monkeypatch.setattr(
        "app.routers.ads._fetch_verifier_keys", fake_fetch_keys
    )

    r = await client.post("/api/v1/auth/register", json={
        "email": "rc1@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    user_id = _user_id_from_jwt(token)
    headers = {"Authorization": f"Bearer {token}"}

    # Issue a token + fire the SSV callback
    r = await client.post(
        "/api/v1/ads/request-token",
        headers=headers,
        json={"ad_unit": "rewarded_android"},
    )
    custom_data = r.json()["custom_data"]

    callback_params = [
        ("ad_network", "admob"),
        ("ad_unit", "ca-app-pub-xxx/yyy"),
        ("reward_amount", "9"),
        ("reward_item", "points"),
        ("user_id", str(user_id)),
        ("transaction_id", "rc-tx-001"),
        ("custom_data", custom_data),
        ("key_id", "1234"),
    ]
    encoded_entries, _ = _build_ssv_qs(callback_params)
    sig = sign(encoded_entries)
    # `quote_plus` URL-encodes `+` (which appears in base64 output) to
    # `%2B` so it survives the round trip through `request.url.query`.
    # Without this, httpx decodes `+` to a space, corrupting the
    # signature bytes.
    from urllib.parse import quote_plus
    qs = urlencode(callback_params) + f"&signature={quote_plus(sig)}"
    r = await client.get(f"/api/v1/ads/google/callback?{qs}")
    assert r.status_code == 200
    assert r.json()["status"] == "credited"

    # Recent credits returns the row
    since = "2020-01-01T00:00:00"
    r = await client.get(
        f"/api/v1/ads/recent-credits?since={since}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["ad_unit"] == "rewarded_android"
    assert body[0]["points_credited"] == 9


# ── Legacy endpoints are 410 Gone ─────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_credit_endpoint_is_410(client):
    """The /ads/credit endpoint is gone — it accepted a client-supplied
    revenue_usd, which is an obvious mint-points attack surface."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "leg1@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/credit",
        headers=headers,
        json={
            "ad_unit": "rewarded_android",
            "provider": "mock",
            "revenue_usd": 1000.0,  # would have minted 100M+ points
            "transaction_id": "forged-tx",
        },
    )
    assert r.status_code == 410, r.text


@pytest.mark.asyncio
async def test_legacy_reward_claim_endpoint_is_410(client):
    """The /ads/reward-claim endpoint is gone — same attack surface
    as /ads/credit."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "leg2@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/reward-claim",
        headers=headers,
        json={
            "ad_unit": "rewarded_android",
            "ad_type": "rewarded",
            "provider": "mock",
            "revenue_usd": 1000.0,
            "transaction_id": "forged-tx-2",
        },
    )
    assert r.status_code == 410, r.text


@pytest.mark.asyncio
async def test_legacy_impression_endpoint_is_410(client):
    """The /ads/impression endpoint is gone."""
    r = await client.post("/api/v1/auth/register", json={
        "email": "leg3@example.com",
        "password": "secure1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/ads/impression",
        headers=headers,
        json={
            "ad_unit": "rewarded_android",
            "ad_type": "rewarded",
            "provider": "mock",
        },
    )
    assert r.status_code == 410, r.text
