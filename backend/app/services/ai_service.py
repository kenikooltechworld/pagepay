"""AI service: Cloudflare Workers AI integration."""

import base64
import os
import json
import logging
import re
import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

def _get_cloudflare_config() -> tuple[str | None, str | None]:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or getattr(settings, "cloudflare_account_id", None)
    api_key = os.environ.get("CLOUDFLARE_API_TOKEN") or getattr(settings, "cloudflare_api_token", None)
    return account_id, api_key


CLOUDFLARE_MODEL = "@cf/zai-org/glm-4.7-flash"


def _extract_text(result: dict) -> str:
    """Extract text from Cloudflare response."""
    if not isinstance(result, dict):
        return ""
    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        for key in ("content", "text"):
            val = message.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for key in ("response", "content", "text"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


AI_TIMEOUT = httpx.Timeout(connect=15.0, read=600.0, write=60.0, pool=15.0)


async def call_ai(prompt: str, max_tokens: int = 4000) -> str:
    """Call Cloudflare Workers AI and return response text."""
    account_id, api_key = _get_cloudflare_config()
    if not account_id or not api_key:
        logger.error("ai.call misconfigured: missing CLOUDFLARE_ACCOUNT_ID/API_TOKEN")
        raise HTTPException(status_code=503, detail="AI service is not configured")

    base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    logger.info("ai.call start model=%s prompt_len=%s max_tokens=%s", CLOUDFLARE_MODEL, len(prompt or ""), max_tokens)

    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            resp = await client.post(
                f"{base_url}/{CLOUDFLARE_MODEL}",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("ai.call failed status=%s body=%s", resp.status_code, resp.text[:300])
                raise HTTPException(status_code=502, detail=f"AI service returned an error (status {resp.status_code}). Please try again.")
            result = resp.json().get("result", {})
            text = _extract_text(result)
            if not text:
                logger.error("ai.call empty response model=%s", CLOUDFLARE_MODEL)
                raise HTTPException(status_code=502, detail="AI service returned an empty response. Please try again.")
            logger.info("ai.call ok model=%s response_len=%s", CLOUDFLARE_MODEL, len(text))
            return text
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("ai.call timeout model=%s prompt_len=%s", CLOUDFLARE_MODEL, len(prompt or ""))
        raise HTTPException(status_code=502, detail="AI request timed out while processing the study material. Please try again.")
    except Exception as exc:
        logger.exception("ai.call error model=%s: %s", CLOUDFLARE_MODEL, exc)
        raise HTTPException(status_code=502, detail=f"AI processing failed: {type(exc).__name__}. Please try again.")


async def call_ai_vision(image_bytes: bytes, content_type: str, prompt: str) -> str:
    """Use Cloudflare Workers AI vision to extract study content from an image."""
    account_id, api_key = _get_cloudflare_config()
    if not account_id or not api_key:
        logger.error("ai.vision misconfigured: missing CLOUDFLARE_ACCOUNT_ID/API_TOKEN")
        raise HTTPException(status_code=503, detail="AI vision service is not configured")

    image = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    model = "@cf/meta/llama-3.2-11b-vision-instruct"
    base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/{model}",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            if response.status_code != 200:
                logger.error("ai.vision failed status=%s body=%s", response.status_code, response.text[:300])
                raise HTTPException(status_code=502, detail=f"AI vision service returned an error (status {response.status_code}). Please try again.")
            text = _extract_text(response.json().get("result", {}))
            if not text:
                logger.error("ai.vision empty response model=%s", model)
                raise HTTPException(status_code=502, detail="AI vision service returned no readable text from the image. Please try a clearer image.")
            return text
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("ai.vision timeout model=%s", model)
        raise HTTPException(status_code=502, detail="AI vision request timed out while reading the image. Please try again.")
    except Exception as exc:
        logger.exception("ai.vision error model=%s: %s", model, exc)
        raise HTTPException(status_code=502, detail=f"AI vision processing failed: {type(exc).__name__}. Please try again.")


def _try_load_json_object(s: str) -> dict | None:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = s.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(s[start:])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _repair_truncated_json_object(s: str) -> str | None:
    """Best-effort repair for model output truncated mid-string/value (common with large JSON)."""
    t = s.rstrip()
    if not t:
        return None
    # If the tail looks like an unterminated/partial string, close it.
    suffixes = [
        "", '"', '"]', '"]}', '"]}}', '"}', '"}}', '"}}}',
        '"]\n  }\n}', '"]\n}', '"], "common_pitfalls": [], "next_steps": ""}}',
        '"\n    }\n  ],\n  "outro": {\n    "summary": [],\n    "common_pitfalls": [],\n    "next_steps": ""\n  }\n}',
    ]
    # quick direct attempts
    for suf in suffixes:
        obj = _try_load_json_object(t + suf)
        if obj is not None:
            return t + suf
    # progressively trim from end and try to close object/arrays/strings
    for cut in range(0, min(4000, len(t)), 1):
        base = t[: len(t) - cut].rstrip().rstrip(",")
        if not base:
            break
        for suf in suffixes:
            obj = _try_load_json_object(base + suf)
            if obj is not None:
                return base + suf
    return None


async def parse_json_response(text: str) -> dict:
    """Parse a JSON object from AI response, handling markdown fences/truncation/trailing text."""
    if text is None:
        raise ValueError("AI returned invalid JSON")
    raw = str(text).strip()
    if not raw:
        raise ValueError("AI returned invalid JSON")

    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    candidates = []
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(raw)

    for candidate in candidates:
        if not candidate:
            continue
        obj = _try_load_json_object(candidate)
        if obj is not None:
            return obj
        start = candidate.find("{")
        if start == -1:
            continue
        repaired = _repair_truncated_json_object(candidate[start:])
        if repaired is not None:
            obj = _try_load_json_object(repaired)
            if obj is not None:
                return obj

    raise ValueError("AI returned invalid JSON")
