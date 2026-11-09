"""Wallet controller (OOP) — thin orchestration over WalletService."""

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.wallet_service import WalletService


class WalletController:
    def __init__(self, db):
        self.wallet = WalletService(db)

    def _require_grant_secret(self, provided: str) -> None:
        if not settings.wallet_grant_secret or provided != settings.wallet_grant_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing grant secret")

    async def balance(self, user_id: int) -> dict:
        return await self.wallet.get_balance(user_id)

    async def transactions(self, user_id: int, currency: str | None, limit: int, cursor: int | None) -> dict:
        return await self.wallet.list_transactions(user_id, currency, limit, cursor)

    async def claim_ad_reward(self, user_id: int, claim_id: str, amount_sp: int) -> dict:
        return await self.wallet.claim_ad_reward(user_id, claim_id, amount_sp)

    async def convert_cb_to_sp(self, user_id: int, amount_cb_kobo: int) -> dict:
        return await self.wallet.convert_cb_to_sp(user_id, amount_cb_kobo)

    async def grant_cb(self, user_id: int, amount_cb_kobo: int, reference: str, grant_secret: str) -> dict:
        self._require_grant_secret(grant_secret)
        return await self.wallet.grant_cb(user_id, amount_cb_kobo, reference)

    async def grant_sp_purchase(self, user_id: int, amount_sp: int, reference: str, grant_secret: str) -> dict:
        self._require_grant_secret(grant_secret)
        return await self.wallet.grant_sp_purchase(user_id, amount_sp, reference)
