"""AI service: Cloudflare Workers AI integration."""

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
        raise HTTPException(status_code=503, detail="AI service not configured")

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{CLOUDFLARE_BASE_URL}/{CLOUDFLARE_MODEL}",
                headers={"Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}"},
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("Cloudflare AI failed: %s %s", resp.status_code, resp.text[:200])
                raise HTTPException(status_code=502, detail="AI service unavailable")
            result = resp.json().get("result", {})
            text = _extract_text(result)
            if not text:
                raise HTTPException(status_code=502, detail="AI returned empty response")
            return text
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("AI call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {str(exc)[:100]}")


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
