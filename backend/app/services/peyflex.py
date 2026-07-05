"""Peyflex VTU API client.

Phase 8 — Bills & Earn. Wraps the Peyflex API for airtime, data,
electricity, and cable TV purchases.

`httpx.AsyncClient` is reused across calls. Module-level singleton
built lazily on first use.

Reference: https://peyflex.com.ng (API docs at portal.peyflex.com.ng)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")

_PEYFLEX_BASE_URL = "https://portal.peyflex.com.ng/api/v1"
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
            "Authorization": api_key,
            "source-domain": "pagepay.app",
        }

    async def _post(self, endpoint: str, params: dict) -> dict:
        """Make a POST to Peyflex and return the JSON body."""
        url = f"{_PEYFLEX_BASE_URL}/{endpoint}"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, params=params, headers=self._headers)
        if resp.status_code != 200:
            raise PeyflexError(
                f"Peyflex returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    async def buy_airtime(
        self, phone: str, amount_naira: int, network: str,
    ) -> PurchaseReceipt:
        """Purchase airtime. Network: mtn_airtime, airtel_airtime, glo_airtime, 9mobile_airtime."""
        body = await self._post("airtime", {
            "format": "json",
            "phone": phone,
            "amount": str(amount_naira),
            "network": f"{network}_airtime",
        })
        return PurchaseReceipt(
            status="success" if body.get("status") == "success" else "failed",
            external_ref=str(body.get("ref", "")),
            message=str(body.get("message", "")),
        )

    async def buy_data(
        self, phone: str, data_id: str, network: str,
    ) -> PurchaseReceipt:
        """Purchase data bundle. Network: mtn_sme_data, airtel_data, glo_data, 9mobile_data."""
        body = await self._post("data", {
            "format": "json",
            "phone": phone,
            "amount": data_id,
            "network": network,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") == "success" else "failed",
            external_ref=str(body.get("ref", "")),
            message=str(body.get("message", "")),
        )

    # ── Electricity ──────────────────────────────────────────────────

    async def check_meter(
        self, meter_number: str, disco: str,
    ) -> dict:
        """Validate a meter number with the DISCO. Returns customer info dict.

        DISCO values: aedc, ekedc, ibedc, ikedc, jed, kaedco, kedco, phed.
        """
        body = await self._post("check-meter", {
            "format": "json",
            "meter_no": meter_number,
            "disco": disco,
        })
        return body

    async def buy_electricity(
        self, meter_number: str, disco: str, meter_type: str, amount_naira: int,
    ) -> PurchaseReceipt:
        """Purchase electricity tokens. meter_type: prepaid | postpaid."""
        body = await self._post("electricity", {
            "format": "json",
            "meter_no": meter_number,
            "disco": disco,
            "meter_type": meter_type,
            "amount": str(amount_naira),
        })
        return PurchaseReceipt(
            status="success" if body.get("status") == "success" else "failed",
            external_ref=str(body.get("ref", "")),
            message=str(body.get("message", "")),
        )

    # ── Cable TV ─────────────────────────────────────────────────────

    async def check_cable_customer(
        self, smartcard_number: str, service: str,
    ) -> dict:
        """Validate a smartcard/IUC number. service: dstv, gotv, startimes.

        Returns customer_name, smart_no, status, customer_number, invoice, etc.
        """
        body = await self._post("check-cable-customer", {
            "format": "json",
            "smart_no": smartcard_number,
            "service": service,
        })
        return body

    async def buy_tv(
        self, smartcard_number: str, service: str, variation_id: str,
    ) -> PurchaseReceipt:
        """Subscribe cable TV. variation_id is the bouquet code."""
        body = await self._post("cable", {
            "format": "json",
            "smart_no": smartcard_number,
            "service": service,
            "variation_id": variation_id,
        })
        return PurchaseReceipt(
            status="success" if body.get("status") == "success" else "failed",
            external_ref=str(body.get("ref", "")),
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
