"""Pydantic schemas for study unlock endpoints."""

from pydantic import BaseModel


class UnlockResponse(BaseModel):
    unlocked: bool
    asset_id: int
    material_id: int
    points_spent: int
    new_sp_balance: int
    content: dict | None = None
    method: str = "points"
