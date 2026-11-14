"""AI service: Cloudflare Workers AI integration."""

import base64
import os
import json
import logging
import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_AI_API_KEY = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run"
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


async def call_ai(prompt: str, max_tokens: int = 4000) -> str:
    """Call Cloudflare Workers AI and return response text."""
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_AI_API_KEY:
        logger.error("ai.call misconfigured: missing CLOUDFLARE_ACCOUNT_ID/API_TOKEN")
        raise HTTPException(status_code=503, detail="AI service not configured")

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    logger.info("ai.call start model=%s prompt_len=%s max_tokens=%s", CLOUDFLARE_MODEL, len(prompt or ""), max_tokens)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{CLOUDFLARE_BASE_URL}/{CLOUDFLARE_MODEL}",
                headers={"Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}"},
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("ai.call failed status=%s body=%s", resp.status_code, resp.text[:300])
                raise HTTPException(status_code=502, detail="AI service unavailable")
            result = resp.json().get("result", {})
            text = _extract_text(result)
            if not text:
                logger.error("ai.call empty response model=%s", CLOUDFLARE_MODEL)
                raise HTTPException(status_code=502, detail="AI returned empty response")
            logger.info("ai.call ok model=%s response_len=%s", CLOUDFLARE_MODEL, len(text))
            return text
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ai.call error model=%s: %s", CLOUDFLARE_MODEL, exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {str(exc)[:100]}")


async def call_ai_vision(image_bytes: bytes, content_type: str, prompt: str) -> str:
    """Use Cloudflare Workers AI vision to extract study content from an image."""
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_AI_API_KEY:
        logger.error("ai.vision misconfigured: missing CLOUDFLARE_ACCOUNT_ID/API_TOKEN")
        raise HTTPException(status_code=503, detail="AI vision service not configured")

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
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{CLOUDFLARE_BASE_URL}/{model}",
                headers={"Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}"},
                json=payload,
            )
            if response.status_code != 200:
                logger.error("ai.vision failed status=%s body=%s", response.status_code, response.text[:300])
                raise HTTPException(status_code=502, detail="AI vision service unavailable")
            text = _extract_text(response.json().get("result", {}))
            if not text:
                logger.error("ai.vision empty response model=%s", model)
                raise HTTPException(status_code=502, detail="AI vision returned empty text")
            return text
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ai.vision error model=%s: %s", model, exc)
        raise HTTPException(status_code=502, detail=f"AI vision error: {str(exc)[:100]}")


async def parse_json_response(text: str) -> dict:
    """Parse JSON from AI response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError("AI returned invalid JSON")
