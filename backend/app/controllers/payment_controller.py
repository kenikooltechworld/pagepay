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
from app.services.paystack_service import (
    PaystackError,
    create_refund,
    initialize_transaction,
    verify_transaction,
    verify_webhook_signature,
)
from app.services.wallet_service import WalletService

logger = logging.getLogger("uvicorn.error")


class PaymentController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet = WalletService(db)

    async def init_wallet_deposit(self, current_user: User, amount_kobo: int) -> dict:
        logger.info("paystack.deposit.init start user=%s amount_kobo=%s", current_user.id, amount_kobo)
        min_kobo = max(100, int(getattr(settings, "wallet_deposit_min_kobo", 10000) or 10000))
        if amount_kobo < min_kobo:
            raise HTTPException(status_code=400, detail=f"Minimum deposit is {min_kobo} kobo (₦{min_kobo / 100:g})")
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
                callback_url=callback_url, metadata=metadata, channels=["card", "bank", "ussd", "bank_transfer"],
            )
        except PaystackError as exc:
            logger.exception("paystack.deposit.init provider error user=%s ref=%s: %s", current_user.id, reference, exc)
            raise HTTPException(status_code=502, detail="Payment provider unavailable")

        payment = Payment(
            user_id=current_user.id, purpose="wallet_deposit_cb", tier="wallet_deposit_cb", amount_kobo=amount_kobo,
            credit_amount_kobo=amount_kobo, currency="NGN", provider="paystack", provider_tx_ref=reference,
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
        if not reference:
            return {"received": True, "handled": False, "reason": "missing_reference"}

        status_norm = str(data_status or "").lower()
        if status_norm != "success":
            logger.info("paystack.apply_charge not successful source=%s ref=%s status=%s", source, reference, status_norm)
            payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
            if payment and payment.status not in ("success", "refunded"):
                if status_norm in ("failed", "abandoned", "reversed"):
                    payment.status = "failed"
                    meta = dict(payment.payment_metadata or {})
                    meta[f"{source}_status"] = {"status": status_norm, "at": datetime.utcnow().isoformat()}
                    payment.payment_metadata = meta
                    await self.db.commit()
            return {"received": True, "handled": False, "reason": "not_success", "status": status_norm, "reference": reference}

        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment:
            logger.warning("paystack.apply_charge unknown reference=%s source=%s", reference, source)
            return {"received": True, "handled": False, "reason": "unknown_reference", "reference": reference}

        if payment.status == "refunded":
            logger.warning("paystack.apply_charge refused: payment refunded ref=%s", reference)
            return {"received": True, "handled": False, "reason": "refunded", "reference": reference}

        if payment.webhook_confirmed and payment.status == "success":
            logger.info("paystack.apply_charge duplicate reference=%s payment_id=%s source=%s", reference, payment.id, source)
            return {"received": True, "handled": True, "reason": "duplicate", "reference": reference}

        if payment.purpose not in (None, "wallet_deposit_cb") and payment.tier != "wallet_deposit_cb":
            logger.warning("paystack.apply_charge unsupported purpose=%s tier=%s ref=%s", payment.purpose, payment.tier, reference)
            return {"received": True, "handled": False, "reason": "unsupported_purpose", "reference": reference}

        if amount_kobo is not None and int(amount_kobo) != int(payment.amount_kobo):
            logger.error("paystack.apply_charge amount mismatch ref=%s paid=%s expected=%s", reference, amount_kobo, payment.amount_kobo)
            payment.status = "amount_mismatch"
            meta = dict(payment.payment_metadata or {})
            meta["amount_mismatch"] = {"paid_kobo": int(amount_kobo), "expected_kobo": int(payment.amount_kobo), "at": datetime.utcnow().isoformat()}
            payment.payment_metadata = meta
            await self.db.commit()
            return {"received": True, "handled": False, "reason": "amount_mismatch", "reference": reference}

        credit_kobo = int(payment.credit_amount_kobo or payment.amount_kobo or 0)
        logger.info("paystack.apply_charge crediting user=%s ref=%s credit_kobo=%s paid_kobo=%s payment_id=%s source=%s", payment.user_id, reference, credit_kobo, amount_kobo, payment.id, source)
        credit_res = await self.wallet.credit_wallet_deposit(
            payment.user_id, credit_kobo, reference,
            metadata={"paystack_reference": reference, "payment_id": payment.id, "purpose": payment.purpose or "wallet_deposit_cb", "source": source},
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

    async def _apply_refund(self, *, reference: str, event_name: str, amount_kobo: int | None, source: str) -> dict:
        reference = (reference or "").strip()
        logger.info("paystack.apply_refund source=%s event=%s ref=%s amount_kobo=%s", source, event_name, reference, amount_kobo)
        if not reference:
            return {"received": True, "handled": False, "reason": "missing_reference"}
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment:
            logger.warning("paystack.apply_refund unknown reference=%s", reference)
            return {"received": True, "handled": False, "reason": "unknown_reference", "reference": reference}

        meta = dict(payment.payment_metadata or {})
        meta.setdefault("refund_events", []).append({"event": event_name, "amount_kobo": amount_kobo, "at": datetime.utcnow().isoformat(), "source": source})
        payment.payment_metadata = meta

        if event_name in ("refund.processed", "refund.processing", "refund.pending"):
            debit_kobo = int(amount_kobo or payment.credit_amount_kobo or payment.amount_kobo or 0)
            if payment.status in ("success", "refunded"):
                debit_res = await self.wallet.debit_wallet_refund(
                    payment.user_id, debit_kobo, reference,
                    metadata={"paystack_reference": reference, "payment_id": payment.id, "event": event_name, "source": source},
                )
                meta = dict(payment.payment_metadata or {})
                meta["refund_debit"] = debit_res
                payment.payment_metadata = meta
                if event_name == "refund.processed":
                    payment.status = "refunded"
                    payment.webhook_confirmed = True
                else:
                    payment.status = "refund_pending" if payment.status != "refunded" else "refunded"
                await self.db.commit()
                logger.info("paystack.apply_refund handled user=%s ref=%s status=%s debit_applied=%s", payment.user_id, reference, payment.status, debit_res.get("applied"))
                return {"received": True, "handled": True, "event": event_name, "reference": reference, "payment_status": payment.status, "debit": debit_res}
            payment.status = "refund_pending" if event_name != "refund.processed" else "refunded"
            await self.db.commit()
            logger.info("paystack.apply_refund recorded (no debit path needed) ref=%s status=%s", reference, payment.status)
            return {"received": True, "handled": True, "event": event_name, "reference": reference, "payment_status": payment.status}

        if event_name in ("refund.failed", "refund.needs-attention"):
            if payment.status != "refunded":
                payment.status = "refund_failed"
            await self.db.commit()
            logger.warning("paystack.apply_refund failed event=%s ref=%s status=%s", event_name, reference, payment.status)
            return {"received": True, "handled": True, "event": event_name, "reference": reference, "payment_status": payment.status}

        await self.db.commit()
        return {"received": True, "handled": False, "event": event_name, "reference": reference}

    async def _apply_charge_failed(self, *, reference: str, source: str, gateway_response: str | None = None) -> dict:
        reference = (reference or "").strip()
        logger.info("paystack.charge_failed source=%s ref=%s gateway=%s", source, reference, gateway_response)
        if not reference:
            return {"received": True, "handled": False, "reason": "missing_reference"}
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment:
            logger.warning("paystack.charge_failed unknown reference=%s", reference)
            return {"received": True, "handled": False, "reason": "unknown_reference", "reference": reference}
        if payment.status in ("success", "refunded"):
            logger.warning("paystack.charge_failed ignored (already %s) ref=%s", payment.status, reference)
            return {"received": True, "handled": False, "reason": f"already_{payment.status}", "reference": reference}
        payment.status = "failed"
        meta = dict(payment.payment_metadata or {})
        meta["charge_failed"] = {"source": source, "gateway_response": gateway_response, "at": datetime.utcnow().isoformat()}
        payment.payment_metadata = meta
        await self.db.commit()
        logger.info("paystack.charge_failed recorded ref=%s user=%s", reference, payment.user_id)
        return {"received": True, "handled": True, "event": "charge.failed", "reference": reference, "payment_status": "failed"}

    async def handle_webhook(self, request: Request) -> dict:
        raw = await request.body()
        sig = request.headers.get("X-Paystack-Signature") or request.headers.get("x-paystack-signature")
        logger.info("paystack.webhook received bytes=%s sig_present=%s ct=%s x-forwarded-event=%s", len(raw), bool(sig), request.headers.get("content-type"), request.headers.get("x-forwarded-event"))
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
        # refund webhooks may nest transaction reference
        reference = str(data.get("reference") or (data.get("transaction") or {}).get("reference") if isinstance(data.get("transaction"), dict) else (data.get("transaction_reference") or "")).strip()
        logger.info("paystack.webhook event=%s reference=%s data_status=%s amount=%s channel=%s currency=%s", event_name, reference, data.get("status"), data.get("amount"), data.get("channel"), data.get("currency"))

        if event_name == "charge.success":
            return await self._apply_verified_charge(reference=reference, data_status=str(data.get("status") or "success"), amount_kobo=data.get("amount"), source="webhook")
        if event_name == "charge.failed":
            return await self._apply_charge_failed(reference=reference, source="webhook", gateway_response=str(data.get("gateway_response") or ""))
        if event_name.startswith("refund."):
            return await self._apply_refund(reference=reference, event_name=event_name, amount_kobo=data.get("amount"), source="webhook")

        logger.info("paystack.webhook ignored event=%s ref=%s", event_name, reference)
        return {"received": True, "handled": False, "event": event_name, "reference": reference}

    async def initiate_refund(self, *, actor_user: User, reference: str, amount_kobo: int | None, reason: str | None, guard_secret: str | None) -> dict:
        """Initiate Paystack refund for a wallet deposit (guarded; idempotent/safe status updates)."""
        # Guard: allow if wallet_grant_secret matches, or (future) admin role. Minimal/surgical guard for now.
        secret_ok = bool(getattr(settings, "wallet_grant_secret", None)) and guard_secret == getattr(settings, "wallet_grant_secret", None)
        is_admin = getattr(actor_user, "role", None) == "admin"
        if not (secret_ok or is_admin):
            logger.warning("paystack.refund.initiate denied user=%s ref=%s", actor_user.id, reference)
            raise HTTPException(status_code=403, detail="Refund not permitted")
        reference = (reference or "").strip()
        logger.info("paystack.refund.initiate start actor=%s ref=%s amount_kobo=%s reason=%s", actor_user.id, reference, amount_kobo, reason)
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        if payment.status in ("refunded", "refund_pending"):
            logger.info("paystack.refund.initiate duplicate/already ref=%s status=%s", reference, payment.status)
            return {"ok": True, "reference": reference, "status": payment.status, "duplicate": True}
        if payment.status != "success":
            raise HTTPException(status_code=400, detail=f"Only successful payments can be refunded (status={payment.status})")
        refund_amt = int(amount_kobo) if amount_kobo is not None else int(payment.amount_kobo)
        if refund_amt <= 0 or refund_amt > int(payment.amount_kobo):
            raise HTTPException(status_code=400, detail="Invalid refund amount")
        try:
            data = await create_refund(reference=reference, amount_kobo=refund_amt, merchant_note=(reason or "PagePay wallet deposit refund")[:200])
        except PaystackError as exc:
            logger.exception("paystack.refund.initiate provider error ref=%s: %s", reference, exc)
            raise HTTPException(status_code=502, detail="Refund provider unavailable")
        meta = dict(payment.payment_metadata or {})
        meta["refund_request"] = {"actor_user_id": actor_user.id, "amount_kobo": refund_amt, "reason": reason, "at": datetime.utcnow().isoformat(), "provider": data}
        payment.payment_metadata = meta
        payment.status = "refund_pending"
        await self.db.commit()
        logger.info("paystack.refund.initiate ok ref=%s refund_status=%s amount_kobo=%s", reference, data.get("status"), refund_amt)
        return {"ok": True, "reference": reference, "status": "refund_pending", "refund": {"amount_kobo": refund_amt, "provider_status": data.get("status"), "id": data.get("id")}}

    async def get_payment_status(self, current_user: User, reference: str) -> dict:
        reference = (reference or "").strip()
        logger.info("paystack.payment.status user=%s ref=%s", current_user.id, reference)
        payment = (await self.db.execute(select(Payment).where(Payment.provider_tx_ref == reference))).scalar_one_or_none()
        if not payment or payment.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Payment not found")
        return {
            "reference": payment.provider_tx_ref,
            "status": payment.status,
            "purpose": payment.purpose,
            "amount_kobo": payment.amount_kobo,
            "credit_amount_kobo": payment.credit_amount_kobo,
            "currency": payment.currency,
            "webhook_confirmed": payment.webhook_confirmed,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        }

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
