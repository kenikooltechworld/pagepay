"""Socket.IO server for real-time updates."""

import socketio
from typing import Dict, Set

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

connected_users: Dict[int, Set[str]] = {}


@sio.event
async def connect(sid, environ, auth):
    print(f"Client connected: {sid}")


@sio.event
async def authenticate(sid, data):
    user_id = data.get("user_id") if isinstance(data, dict) else None
    if not user_id:
        await sio.disconnect(sid)
        return
    await sio.enter_room(sid, f"user_{user_id}")
    connected_users.setdefault(user_id, set()).add(sid)
    print(f"User {user_id} authenticated (sid: {sid})")


@sio.event
async def disconnect(sid):
    for user_id, sids in list(connected_users.items()):
        if sid in sids:
            sids.discard(sid)
            if not sids:
                del connected_users[user_id]
            print(f"User {user_id} disconnected (sid: {sid})")
            break
    print(f"Client disconnected: {sid}")


async def emit_to_user(user_id: int, event: str, data: dict):
    await sio.emit(event, data, room=f"user_{user_id}")


async def emit_notification(user_id: int, notification: dict):
    await emit_to_user(user_id, "notification", notification)
