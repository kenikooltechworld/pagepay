"""Wallet controller (OOP) — thin orchestration over WalletService."""

import logging

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.wallet_service import WalletService

logger = logging.getLogger("uvicorn.error")


class WalletController:
    def __init__(self, db):
        self.wallet = WalletService(db)

    def _require_grant_secret(self, provided: str) -> None:
        if not settings.wallet_grant_secret or provided != settings.wallet_grant_secret:
            logger.warning("endpoint.wallet.grant denied: invalid/missing grant secret")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing grant secret")

    async def balance(self, user_id: int) -> dict:
        logger.info("wallet.balance user=%s", user_id)
        res = await self.wallet.get_balance(user_id)
        logger.info("wallet.balance result user=%s sp=%s cb_kobo=%s", user_id, res.get("service_points_sp"), res.get("cashable_balance_cb_kobo"))
        return res

    async def transactions(self, user_id: int, currency: str | None, limit: int, cursor: int | None) -> dict:
        logger.info("wallet.transactions user=%s currency=%s limit=%s cursor=%s", user_id, currency, limit, cursor)
        res = await self.wallet.list_transactions(user_id, currency, limit, cursor)
        logger.info("wallet.transactions result user=%s count=%s next_cursor=%s", user_id, len(res.get("items", [])), res.get("next_cursor"))
        return res

    async def claim_ad_reward(self, user_id: int, claim_id: str, amount_sp: int) -> dict:
        logger.info("wallet.ad_reward user=%s claim_id=%s amount_sp=%s", user_id, claim_id, amount_sp)
        res = await self.wallet.claim_ad_reward(user_id, claim_id, amount_sp)
        logger.info("wallet.ad_reward result user=%s applied=%s balance_sp=%s", user_id, res.get("applied"), res.get("balance_sp"))
        return res

    async def convert_cb_to_sp(self, user_id: int, amount_cb_kobo: int) -> dict:
        logger.info("wallet.convert_cb_to_sp user=%s amount_cb_kobo=%s", user_id, amount_cb_kobo)
        res = await self.wallet.convert_cb_to_sp(user_id, amount_cb_kobo)
        logger.info("wallet.convert_cb_to_sp result user=%s credited_sp=%s cb=%s sp=%s", user_id, res.get("credited_sp"), res.get("balance_cb_kobo"), res.get("balance_sp"))
        return res

    async def grant_cb(self, user_id: int, amount_cb_kobo: int, reference: str, grant_secret: str) -> dict:
        self._require_grant_secret(grant_secret)
        logger.info("wallet.grant_cb user=%s amount_cb_kobo=%s ref=%s", user_id, amount_cb_kobo, reference)
        return await self.wallet.grant_cb(user_id, amount_cb_kobo, reference)

    async def grant_sp_purchase(self, user_id: int, amount_sp: int, reference: str, grant_secret: str) -> dict:
        self._require_grant_secret(grant_secret)
        logger.info("wallet.grant_sp_purchase user=%s amount_sp=%s ref=%s", user_id, amount_sp, reference)
        return await self.wallet.grant_sp_purchase(user_id, amount_sp, reference)
