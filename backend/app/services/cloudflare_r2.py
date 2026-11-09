"""Cloudflare R2 storage service (S3-compatible).

Teaching notes:
- R2 is S3-compatible, so we use boto3 with the Cloudflare S3 API endpoint.
- Media is stored as base64 from the client; we decode, compress (images),
  and upload. Public URLs come from CLOUDFLARE_R2_PUBLIC_URL.
- Compression happens BEFORE upload to keep the stored object small.
"""

import base64
import io
import logging
import uuid
from urllib.parse import urlparse


from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class CloudflareR2Service:
    """Service for uploading/compressing media to Cloudflare R2."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.client import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.cloudflare_s3_api_endpoint,
                aws_access_key_id=settings.cloudflare_access_key,
                aws_secret_access_key=settings.cloudflare_secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )
        return self._client

    # --- helpers ---

    @staticmethod
    def decode_base64(data_url: str) -> bytes:
        """Decode a data URL (e.g. data:image/png;base64,...) to raw bytes."""

        if not data_url:
            raise ValueError("Empty image data")
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        return base64.b64decode(data_url)

    @staticmethod
    def compress_image(data: bytes, max_size: int = 1_048_576, quality: int = 85) -> bytes:
        """Compress an image to under max_size bytes.

        Tries JPEG (most common for photos/avatars). Falls back to original
        bytes if Pillow is unavailable or the image is already small.
        """

        try:
            from PIL import Image
        except ImportError:
            return data

        try:
            img = Image.open(io.BytesIO(data))
            # Convert to RGB (JPEG has no alpha) if needed.
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGBA")
                # Composite onto white background so transparency becomes white.
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(background, img).convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()
            return compressed if len(compressed) <= max_size else data
        except Exception as exc:
            logger.warning("Image compression failed: %s", exc)
            return data

    @staticmethod
    def _filename(ext: str) -> str:
        return f"{uuid.uuid4().hex}{ext}"

    def _public_url(self, key: str) -> str:
        base = settings.cloudflare_r2_public_url.rstrip("/")
        return f"{base}/{key}"

    # --- public API ---

    def upload_base64(self, data_url: str, folder: str = "pagepay/avatars") -> str:
        """Decode, compress (if image), upload to R2, return public URL."""

        raw = self.decode_base64(data_url)
        is_image = data_url.split(",", 1)[0].lower().startswith("data:image") if "," in data_url.lower() else False
        if is_image:
            raw = self.compress_image(raw)
        ext = ".jpg" if is_image else ".bin"
        key = f"{folder}/{self._filename(ext)}"
        self.client.put_object(
            Bucket=settings.cloudflare_bucket,
            Key=key,
            Body=raw,
            ContentType="image/jpeg" if is_image else "application/octet-stream",
        )
        return self._public_url(key)

    def upload_bytes(self, data: bytes, filename: str, folder: str = "pagepay/uploads") -> str:
        key = f"{folder}/{filename}"
        self.client.put_object(
            Bucket=settings.cloudflare_bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )
        return self._public_url(key)

    def delete(self, public_url: str) -> None:
        """Delete an object by its public URL (best-effort)."""

        try:
            parsed = urlparse(public_url)
            key = parsed.path.lstrip("/")
            self.client.delete_object(Bucket=settings.cloudflare_bucket, Key=key)
        except Exception as exc:
            # ClientError (botocore) not available locally; catch broadly.
            logger.warning("Failed to delete R2 object %s: %s", public_url, exc)
