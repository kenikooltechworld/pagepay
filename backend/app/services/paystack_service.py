"""Paystack client (minimal) + webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class PaystackError(Exception):
    pass


@dataclass
class InitResult:
    authorization_url: str
    access_code: str
    reference: str


def _secret() -> str:
    key = (settings.paystack_secret_key or "").strip()
    if not key:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured")
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_secret()}", "Content-Type": "application/json"}


async def initialize_transaction(*, email: str, amount_kobo: int, reference: str, callback_url: str | None = None, metadata: dict[str, Any] | None = None, channels: list[str] | None = None) -> InitResult:
    url = f"{settings.paystack_base_url.rstrip('/')}/transaction/initialize"
    payload: dict[str, Any] = {"email": email, "amount": int(amount_kobo), "reference": reference, "currency": "NGN"}
    if callback_url:
        payload["callback_url"] = callback_url
    if metadata:
        payload["metadata"] = metadata
    if channels:
        payload["channels"] = channels
    logger.info("paystack.initialize request reference=%s amount_kobo=%s email=%s channels=%s", reference, amount_kobo, email, channels)
    try:
        async with httpx.AsyncClient(timeout=settings.paystack_http_timeout_seconds) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
    except httpx.HTTPError as exc:
        logger.exception("paystack.initialize network error reference=%s: %s", reference, exc)
        raise PaystackError(f"Paystack request failed: {exc}") from exc
    logger.info("paystack.initialize response reference=%s status=%s body=%s", reference, resp.status_code, resp.text[:500])
    if resp.status_code < 200 or resp.status_code >= 300:
        raise PaystackError(f"Paystack HTTP {resp.status_code}: {resp.text[:300]}")
    body = resp.json() if resp.content else {}
    if not isinstance(body, dict) or body.get("status") is not True:
        raise PaystackError(f"Paystack error: {body!r}")
    data = body.get("data") or {}
    auth = str(data.get("authorization_url") or "")
    if not auth:
        raise PaystackError(f"Paystack missing authorization_url: {body!r}")
    return InitResult(authorization_url=auth, access_code=str(data.get("access_code") or ""), reference=str(data.get("reference") or reference))


async def verify_transaction(reference: str) -> dict[str, Any]:
    """Verify a transaction with Paystack (server-side). Returns data dict."""
    url = f"{settings.paystack_base_url.rstrip('/')}/transaction/verify/{reference}"
    logger.info("paystack.verify request reference=%s", reference)
    try:
        async with httpx.AsyncClient(timeout=settings.paystack_http_timeout_seconds) as client:
            resp = await client.get(url, headers=_headers())
    except httpx.HTTPError as exc:
        logger.exception("paystack.verify network error reference=%s: %s", reference, exc)
        raise PaystackError(f"Paystack request failed: {exc}") from exc
    logger.info("paystack.verify response reference=%s status=%s body=%s", reference, resp.status_code, resp.text[:500])
    if resp.status_code < 200 or resp.status_code >= 300:
        raise PaystackError(f"Paystack HTTP {resp.status_code}: {resp.text[:300]}")
    body = resp.json() if resp.content else {}
    if not isinstance(body, dict) or body.get("status") is not True:
        raise PaystackError(f"Paystack error: {body!r}")
    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise PaystackError(f"Paystack verify missing data: {body!r}")
    return data


async def create_refund(*, reference: str, amount_kobo: int | None = None, merchant_note: str | None = None, customer_note: str | None = None) -> dict[str, Any]:
    """Create a Paystack refund for a transaction (by reference). Returns data dict."""
    url = f"{settings.paystack_base_url.rstrip('/')}/refund"
    payload: dict[str, Any] = {"transaction": reference}
    if amount_kobo is not None:
        payload["amount"] = int(amount_kobo)
    if merchant_note:
        payload["merchant_note"] = merchant_note[:200]
    if customer_note:
        payload["customer_note"] = customer_note[:200]
    logger.info("paystack.refund request reference=%s amount_kobo=%s", reference, amount_kobo)
    try:
        async with httpx.AsyncClient(timeout=settings.paystack_http_timeout_seconds) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
    except httpx.HTTPError as exc:
        logger.exception("paystack.refund network error reference=%s: %s", reference, exc)
        raise PaystackError(f"Paystack request failed: {exc}") from exc
    logger.info("paystack.refund response reference=%s status=%s body=%s", reference, resp.status_code, resp.text[:600])
    if resp.status_code < 200 or resp.status_code >= 300:
        raise PaystackError(f"Paystack HTTP {resp.status_code}: {resp.text[:300]}")
    body = resp.json() if resp.content else {}
    if not isinstance(body, dict) or body.get("status") is not True:
        raise PaystackError(f"Paystack error: {body!r}")
    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise PaystackError(f"Paystack refund missing data: {body!r}")
    return data


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = (settings.paystack_secret_key or "").strip()
    if not signature_header or not secret:
        logger.warning("paystack.webhook signature verify failed: header=%s secret_set=%s", bool(signature_header), bool(secret))
        return False
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    ok = hmac.compare_digest(computed, signature_header.strip())
    if not ok:
        logger.warning("paystack.webhook signature mismatch")
    return ok
