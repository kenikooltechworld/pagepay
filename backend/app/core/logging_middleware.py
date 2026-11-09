"""Request/response logging middleware (redacts secrets)."""

import json
import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("uvicorn.error")

REDACT_KEYS = {"password", "new_password", "current_password", "pin", "new_pin", "current_pin",
               "token", "refresh_token", "access_token", "id_token", "reset_token", "otp", "code",
               "grant_secret", "authorization", "secret", "api_key", "firebase_service_account_key"}
MAX_BODY_LOG = 4000


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if str(k).lower() in REDACT_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj[:50]]
    if isinstance(obj, str) and len(obj) > 500:
        return obj[:500] + f"...(len={len(obj)})"
    return obj


def _safe_body(raw: bytes, content_type: str | None) -> str:
    if not raw:
        return ""
    if content_type and "application/json" in content_type:
        try:
            return json.dumps(_redact(json.loads(raw.decode("utf-8", "ignore"))), ensure_ascii=False)[:MAX_BODY_LOG]
        except Exception:
            pass
    txt = raw.decode("utf-8", "ignore")
    # form redaction
    if "password" in txt or "token" in txt or "secret" in txt:
        return "<redacted-form>"
    return txt[:MAX_BODY_LOG]


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        ct = request.headers.get("content-type")
        # read and replay body
        raw = await request.body()
        req_body = _safe_body(raw, ct)
        logger.info(
            "REQ %s %s query=%s client=%s user_agent=%s body=%s",
            request.method, request.url.path, str(request.query_params)[:500],
            getattr(request.client, "host", None), (request.headers.get("user-agent") or "")[:120], req_body,
        )

        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}
        request = Request(request.scope, receive)

        try:
            response = await call_next(request)
        except Exception:
            dur = (time.perf_counter() - start) * 1000
            logger.exception("ERR %s %s duration_ms=%.1f", request.method, request.url.path, dur)
            raise

        # capture response body (best-effort; skip large/streaming content-types if needed)
        resp_body_chunks = []
        async for chunk in response.body_iterator:
            resp_body_chunks.append(chunk)
        resp_raw = b"".join(resp_body_chunks)
        rct = response.headers.get("content-type")
        resp_log = _safe_body(resp_raw, rct)
        dur = (time.perf_counter() - start) * 1000
        level = logging.INFO if response.status_code < 400 else (logging.WARNING if response.status_code < 500 else logging.ERROR)
        logger.log(level, "RES %s %s status=%s duration_ms=%.1f body=%s",
                   request.method, request.url.path, response.status_code, dur, resp_log)
        return Response(content=resp_raw, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
