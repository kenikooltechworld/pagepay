"""Public config endpoints.

`GET /api/v1/config/ads` — returns the AdMob App ID + unit IDs the
client needs to initialize the SDK and instantiate ad slots. The
client calls this once on app start (before any ad call) and again
on focus after a config rotation.

Anonymous-friendly: the response contains only public ad unit IDs,
no PII. The token, if present, is read so the server can log the
user id with the request (helps debug "user X keeps getting no
ads" tickets), but no auth is enforced.

The env switch: `?env=dev|prod`. The client passes `env=dev` from
an `__DEV__` build, `env=prod` from a release build. Server-side
fallback: if the env param is omitted, the response is `prod`
(the seeded default).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ads import fetch_ads_config


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/config", tags=["config"])


@router.get("/ads")
async def get_ads_config(
    env: str = Query(
        "prod",
        description="dev|prod. Dev returns Google's documented test unit IDs; "
                    "prod returns the real PagePay publisher IDs.",
        pattern="^(dev|prod)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return the AdMob App ID + unit IDs for one environment.

    Shape: flat dict keyed by slot. Example (dev):
        {
          "android_app_id":       "ca-app-pub-3940256099942544~3347511713",
          "ios_app_id":           "ca-app-pub-3940256099942544~1712483245",
          "in_feed_android":      "ca-app-pub-3940256099942544/2247696110",
          "in_feed_ios":          "ca-app-pub-3940256099942544/2247696110",
          "interstitial_android": "ca-app-pub-3940256099942544/1033173712",
          "interstitial_ios":     "ca-app-pub-3940256099942544/1033173712",
          "rewarded_android":     "ca-app-pub-3940256099942544/5224354917",
          "rewarded_ios":         "ca-app-pub-3940256099942544/5224354917",
          "banner_android":       "ca-app-pub-3940256099942544/6300978111",
          "banner_ios":           "ca-app-pub-3940256099942544/6300978111",
        }

    Missing keys return as empty strings — the client treats that
    as "slot disabled" and degrades to MockAdModal for rewarded,
    no-op for the others.
    """
    config = await fetch_ads_config(db, environment=env)
    logger.info("Served ads config for env=%s (%d keys)", env, len(config))
    return config
