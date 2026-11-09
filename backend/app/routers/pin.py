"""Transaction PIN HTTP routes (thin layer)."""

from fastapi import APIRouter, Depends

from app.controllers.pin_controller import PinController
from app.core.database import get_db
from app.models.user import User
from app.schemas.pin import PinChangeRequest, PinSetupRequest, PinStatusResponse, PinVerifyRequest
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/pin", tags=["pin"])


def get_controller(db=Depends(get_db)) -> PinController:
    return PinController(db)


@router.get("/status", response_model=PinStatusResponse)
async def pin_status(current_user: User = Depends(get_current_user), controller: PinController = Depends(get_controller)):
    return await controller.status(current_user)


@router.post("/setup", status_code=201)
async def setup_pin(payload: PinSetupRequest, current_user: User = Depends(get_current_user), controller: PinController = Depends(get_controller)):
    return await controller.setup(current_user, payload.password, payload.pin)


@router.post("/verify")
async def verify_pin(payload: PinVerifyRequest, current_user: User = Depends(get_current_user), controller: PinController = Depends(get_controller)):
    return await controller.verify(current_user, payload.pin)


@router.post("/change")
async def change_pin(payload: PinChangeRequest, current_user: User = Depends(get_current_user), controller: PinController = Depends(get_controller)):
    return await controller.change(current_user, payload.current_pin, payload.new_pin)
