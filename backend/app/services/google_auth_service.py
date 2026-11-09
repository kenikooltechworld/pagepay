"""Google OAuth service: verifies Google ID tokens."""

import logging

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class GoogleAuthService:
    """Verifies Google ID tokens and returns the verified email."""

    def verify_id_token(self, id_token: str) -> dict:
        if not settings.google_client_id:
            raise ValueError("Google OAuth2 is not configured")

        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token

            idinfo = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                settings.google_client_id,
            )
        except Exception as exc:
            logger.error("Google token verification failed: %s", exc)
            raise ValueError("Invalid Google token")

        email = idinfo.get("email")
        if not email or not idinfo.get("email_verified"):
            raise ValueError("Google account email not verified")

        return {"email": email, "name": idinfo.get("name")}
