"""Transaction PIN controller (OOP)."""

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


class PinController:
    """Orchestrates transaction PIN use-cases."""

    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.auth = AuthService(db)

    async def status(self, current_user: User) -> dict:
        return {"has_pin": current_user.transaction_pin_hash is not None}

    async def setup(self, current_user: User, password: str, pin: str) -> dict:
        if current_user.transaction_pin_hash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PIN already set. Use /pin/change to update it.",
            )
        if not current_user.password_hash or not self.auth.verify_password(password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password.",
            )
        current_user.transaction_pin_hash = self.auth.hash_password(pin)
        await self.users.update(current_user)
        return {"ok": True}

    async def verify(self, current_user: User, pin: str) -> dict:
        if current_user.transaction_pin_hash is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PIN set. Set one in Profile > Security.",
            )
        if not self.auth.verify_password(pin, current_user.transaction_pin_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect PIN.",
            )
        return {"valid": True}

    async def change(self, current_user: User, current_pin: str, new_pin: str) -> dict:
        if current_user.transaction_pin_hash is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PIN set. Set one in Profile > Security.",
            )
        if not self.auth.verify_password(current_pin, current_user.transaction_pin_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect current PIN.",
            )
        current_user.transaction_pin_hash = self.auth.hash_password(new_pin)
        await self.users.update(current_user)
        return {"ok": True}
