"""Paystack deposit + webhook controller."""

import logging
import uuid
from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payment import Payment
from app.models.user import User
from app.services.paystack_service import PaystackError, initialize_transaction, verify_transaction, verify_webhook_signature
from app.services.wallet_service import WalletService

logger = logging.getLogger("uvicorn.error")


class PaymentController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet = WalletService(db)

    async def init_wallet_deposit(self, current_user: User, amount_kobo: int) -> dict:
        logger.info("paystack.deposit.init start user=%s amount_kobo=%s", current_user.id, amount_kobo)
        if amount_kobo < 100:
            raise HTTPException(status_code=400, detail="Minimum deposit is 100 kobo (₦1)")
        if not (settings.paystack_secret_key or "").strip():
            logger.error("paystack.deposit.init missing PAYSTACK_SECRET_KEY")
            raise HTTPException(status_code=503, detail="Payments not configured")
        if not current_user.email:
            raise HTTPException(status_code=400, detail="A verified email is required for payments")

        reference = f"pp_wallet_{current_user.id}_{uuid.uuid4().hex[:16]}"
        callback_url = f"{settings.public_base_url.rstrip('/')}{settings.paystack_callback_path or '/wallet'}"
        metadata = {"user_id": current_user.id, "type": "wallet_deposit_cb", "credit_amount_kobo": amount_kobo}

        try:
            result = await initialize_transaction(
                email=current_user.email, amount_kobo=amount_kobo, reference=reference,
                callback_url=callback_url, metadata=metadata,
            )
        except PaystackError as exc:
            logger.exception("paystack.deposit.init provider error user=%s ref=%s: %s", current_user.id, reference, exc)
            raise HTTPException(status_code=502, detail="Payment provider unavailable")

        payment = Payment(
            user_id=current_user.id, purpose="wallet_deposit_cb", amount_kobo=amount_kobo,
            credit_amount_kobo=amount_kobo, provider="paystack", provider_tx_ref=reference,
            status="pending", webhook_confirmed=False, payment_metadata=metadata,
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        logger.info("paystack.deposit.init ok user=%s ref=%s payment_id=%s auth_url_set=%s", current_user.id, reference, payment.id, bool(result.authorization_url))
        return {
            "authorization_url": result.authorization_url,
            "access_code": result.access_code,
            "reference": reference,
            "amount_kobo": amount_kobo,
            "credit_amount_kobo": amount_kobo,
            "currency": "NGN",
        }

    async def _apply_verified_charge(self, *, reference: str, data_status: str | None, amount_kobo: int | None, source: str) -> dict:
        """Idempotently credit CB for a verified Paystack charge (shared by webhook + verify endpoint)."""
        reference = (reference or "").strip()
        logger.info("paystack.apply_charge source=%s ref=%s data_status=%s amount=%s", source, reference, data_status, amount_kobo)
        if data_status != "success":
            logger.info("paystack.apply_charge not successful source=%s ref=%s status=%s", source, reference, data_status)
            return {"received": True, "handled": False, "reason": "not_success", "status": data_status, "reference": reference}
        if not reference:
            return {"received": True, "handled": False, "reason": "missing_reference"}

        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment:
            logger.warning("paystack.apply_charge unknown reference=%s source=%s", reference, source)
            return {"received": True, "handled": False, "reason": "unknown_reference", "reference": reference}

        if payment.webhook_confirmed and payment.status == "success":
            logger.info("paystack.apply_charge duplicate reference=%s payment_id=%s source=%s", reference, payment.id, source)
            return {"received": True, "handled": True, "reason": "duplicate", "reference": reference}

        if payment.purpose != "wallet_deposit_cb":
            logger.warning("paystack.apply_charge unsupported purpose=%s ref=%s", payment.purpose, reference)
            return {"received": True, "handled": False, "reason": "unsupported_purpose", "reference": reference}

        if amount_kobo is not None and int(amount_kobo) != int(payment.amount_kobo):
            logger.error("paystack.apply_charge amount mismatch ref=%s paid=%s expected=%s", reference, amount_kobo, payment.amount_kobo)
            return {"received": True, "handled": False, "reason": "amount_mismatch", "reference": reference}

        credit_kobo = int(payment.credit_amount_kobo or payment.amount_kobo or 0)
        logger.info("paystack.apply_charge crediting user=%s ref=%s credit_kobo=%s paid_kobo=%s payment_id=%s source=%s", payment.user_id, reference, credit_kobo, amount_kobo, payment.id, source)
        credit_res = await self.wallet.credit_wallet_deposit(
            payment.user_id, credit_kobo, reference,
            metadata={"paystack_reference": reference, "payment_id": payment.id, "purpose": payment.purpose, "source": source},
        )
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one()
        payment.status = "success"
        payment.webhook_confirmed = True
        payment.confirmed_at = datetime.utcnow()
        meta = dict(payment.payment_metadata or {})
        meta[source] = {"credited": credit_res.get("applied"), "ledger_id": credit_res.get("ledger_id"), "at": datetime.utcnow().isoformat()}
        payment.payment_metadata = meta
        await self.db.commit()
        logger.info("paystack.apply_charge success user=%s ref=%s applied=%s balance_cb_kobo=%s source=%s", payment.user_id, reference, credit_res.get("applied"), credit_res.get("balance_cb_kobo"), source)
        return {"received": True, "handled": True, "reference": reference, "credited": credit_res.get("applied"), "balance_cb_kobo": credit_res.get("balance_cb_kobo")}

    async def handle_webhook(self, request: Request) -> dict:
        raw = await request.body()
        sig = request.headers.get("X-Paystack-Signature") or request.headers.get("x-paystack-signature")
        logger.info("paystack.webhook received bytes=%s sig_present=%s ct=%s", len(raw), bool(sig), request.headers.get("content-type"))
        if not verify_webhook_signature(raw, sig):
            logger.warning("paystack.webhook rejected: invalid signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        try:
            event = __import__("json").loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.exception("paystack.webhook invalid json: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        event_name = str(event.get("event") or "")
        data = event.get("data") or {}
        reference = str(data.get("reference") or "").strip()
        logger.info("paystack.webhook event=%s reference=%s data_status=%s amount=%s", event_name, reference, data.get("status"), data.get("amount"))

        if event_name != "charge.success":
            logger.info("paystack.webhook ignored event=%s ref=%s", event_name, reference)
            return {"received": True, "handled": False, "event": event_name, "reference": reference}

        return await self._apply_verified_charge(reference=reference, data_status=str(data.get("status") or "success"), amount_kobo=data.get("amount"), source="webhook")

    async def verify_reference(self, current_user: User, reference: str) -> dict:
        """Server-verify with Paystack and credit CB if successful (idempotent)."""
        reference = (reference or "").strip()
        logger.info("paystack.verify_ref start user=%s ref=%s", current_user.id, reference)
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment or payment.user_id != current_user.id:
            logger.warning("paystack.verify_ref not found/forbidden user=%s ref=%s", current_user.id, reference)
            raise HTTPException(status_code=404, detail="Payment not found")
        try:
            data = await verify_transaction(reference)
        except PaystackError as exc:
            logger.exception("paystack.verify_ref provider error user=%s ref=%s: %s", current_user.id, reference, exc)
            raise HTTPException(status_code=502, detail="Payment verification unavailable")
        res = await self._apply_verified_charge(reference=reference, data_status=str(data.get("status") or ""), amount_kobo=data.get("amount"), source="verify")
        # ensure ownership context in response
        res["payment_status"] = (await self.db.execute(select(Payment.status).where(Payment.provider_tx_ref == reference))).scalar_one()
        logger.info("paystack.verify_ref done user=%s ref=%s result=%s", current_user.id, reference, {k: res.get(k) for k in ("handled", "credited", "reason", "payment_status")})
        return res
