"""Transaction PIN controller (OOP)."""

import logging

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

logger = logging.getLogger("uvicorn.error")


class PinController:
    """Orchestrates transaction PIN use-cases."""

    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.auth = AuthService(db)

    async def status(self, current_user: User) -> dict:
        has_pin = current_user.transaction_pin_hash is not None
        logger.info("pin.status user=%s has_pin=%s", current_user.id, has_pin)
        return {"has_pin": has_pin}

    async def setup(self, current_user: User, password: str, pin: str) -> dict:
        logger.info("pin.setup start user=%s", current_user.id)
        if current_user.transaction_pin_hash is not None:
            logger.warning("pin.setup conflict user=%s (already set)", current_user.id)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PIN already set. Use /pin/change to update it.")
        if not current_user.password_hash or not self.auth.verify_password(password, current_user.password_hash):
            logger.warning("pin.setup auth failed user=%s (incorrect password)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
        current_user.transaction_pin_hash = self.auth.hash_password(pin)
        await self.users.update(current_user)
        logger.info("pin.setup ok user=%s", current_user.id)
        return {"ok": True}

    async def verify(self, current_user: User, pin: str) -> dict:
        logger.info("pin.verify start user=%s", current_user.id)
        if current_user.transaction_pin_hash is None:
            logger.warning("pin.verify not set user=%s", current_user.id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No PIN set. Set one in Profile > Security.")
        if not self.auth.verify_password(pin, current_user.transaction_pin_hash):
            logger.warning("pin.verify failed user=%s (incorrect pin)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect PIN.")
        logger.info("pin.verify ok user=%s", current_user.id)
        return {"valid": True}

    async def change(self, current_user: User, current_pin: str, new_pin: str) -> dict:
        logger.info("pin.change start user=%s", current_user.id)
        if current_user.transaction_pin_hash is None:
            logger.warning("pin.change not set user=%s", current_user.id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No PIN set. Set one in Profile > Security.")
        if not self.auth.verify_password(current_pin, current_user.transaction_pin_hash):
            logger.warning("pin.change failed user=%s (incorrect current pin)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect current PIN.")
        current_user.transaction_pin_hash = self.auth.hash_password(new_pin)
        await self.users.update(current_user)
        logger.info("pin.change ok user=%s", current_user.id)
        return {"ok": True}
