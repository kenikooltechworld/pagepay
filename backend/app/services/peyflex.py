"""Peyflex VTU API client.

Phase 8 — Bills & Earn. Wraps the Peyflex API for airtime, data,
electricity, and cable TV purchases.

`httpx.AsyncClient` is reused across calls. Module-level singleton
built lazily on first use.

Base URL: https://client.peyflex.com.ng
Auth: Authorization: Token <api_key> (header)
Body: application/json

Reference: https://documenter.getpostman.com/view/17835214/2sB34imLMn
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")

_PEYFLEX_BASE_URL = "https://client.peyflex.com.ng"
_HTTP_TIMEOUT_SECONDS = 15.0


class PeyflexError(Exception):
    """Raised for non-2xx responses or network errors from Peyflex."""


@dataclass
class PurchaseReceipt:
    """Confirmed purchase from Peyflex."""
    status: str  # "success" | "failed"
    external_ref: str
    message: str


class PeyflexClient:
    """HTTP client for the Peyflex VTU API.

    All purchase methods expect the caller to have already debited the
    user's wallet. This service only talks to Peyflex — it does not
    touch the database.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Make a JSON POST to Peyflex and return the JSON body."""
        url = f"{_PEYFLEX_BASE_URL}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload, headers=self._headers)
        if resp.status_code not in (200, 201):
            raise PeyflexError(
                f"Peyflex returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    async def buy_airtime(
        self, phone: str, amount_naira: int, network: str,
    ) -> PurchaseReceipt:
        """Purchase airtime. Network: mtn, airtel, glo, 9mobile."""
        body = await self._post("/api/v1/airtime", {
            "phone": phone,
            "amount": amount_naira,
            "network": network,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") in ("success", True) else "failed",
            external_ref=str(body.get("ref", body.get("reference", ""))),
            message=str(body.get("message", "")),
        )

    async def buy_data(
        self, phone: str, data_id: str, network: str,
    ) -> PurchaseReceipt:
        """Purchase data bundle."""
        body = await self._post("/api/v1/data", {
            "phone": phone,
            "amount": data_id,
            "network": network,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") in ("success", True) else "failed",
            external_ref=str(body.get("ref", body.get("reference", ""))),
            message=str(body.get("message", "")),
        )

    async def check_meter(
        self, meter_number: str, disco: str,
    ) -> dict:
        """Validate a meter number with the DISCO."""
        return await self._post("/api/v1/check-meter", {
            "meter_no": meter_number,
            "disco": disco,
        })

    async def buy_electricity(
        self, meter_number: str, disco: str, meter_type: str, amount_naira: int,
    ) -> PurchaseReceipt:
        """Purchase electricity tokens. meter_type: prepaid | postpaid."""
        body = await self._post("/api/v1/electricity", {
            "meter_no": meter_number,
            "disco": disco,
            "meter_type": meter_type,
            "amount": amount_naira,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") in ("success", True) else "failed",
            external_ref=str(body.get("ref", body.get("reference", ""))),
            message=str(body.get("message", "")),
        )

    async def check_cable_customer(
        self, smartcard_number: str, service: str,
    ) -> dict:
        """Validate a smartcard/IUC number. service: dstv | gotv | startimes."""
        return await self._post("/api/v1/check-cable-customer", {
            "smart_no": smartcard_number,
            "service": service,
        })

    async def buy_tv(
        self, smartcard_number: str, service: str, variation_id: str,
    ) -> PurchaseReceipt:
        """Subscribe cable TV. variation_id is the bouquet plan code."""
        body = await self._post("/api/v1/cable", {
            "smart_no": smartcard_number,
            "service": service,
            "variation_id": variation_id,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") in ("success", True) else "failed",
            external_ref=str(body.get("ref", body.get("reference", ""))),
            message=str(body.get("message", "")),
        )


_client: PeyflexClient | None = None


def get_client() -> PeyflexClient:
    """Lazily-built module-level PeyflexClient singleton."""
    global _client
    if _client is None:
        key = settings.peyflex_api_key
        if not key:
            raise PeyflexError("peyflex_api_key is not configured in settings")
        _client = PeyflexClient(key)
    return _client


def reset_client_for_tests() -> None:
    global _client
    _client = None
