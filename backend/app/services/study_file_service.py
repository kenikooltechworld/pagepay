"""Helpers for extracting text from uploaded study material files."""

import io
from typing import Tuple

from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_MIME_PREFIXES = ("text/",)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",  # some clients send this; validate by extension
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _ext(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def read_upload(upload: UploadFile) -> Tuple[bytes, str, str]:
    """Read and validate an uploaded file. Returns (data, filename, mime_type)."""
    filename = upload.filename or "upload"
    ext = _ext(filename)
    mime = (upload.content_type or "application/octet-stream").lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: pdf, docx, txt, md")
    if mime not in ALLOWED_MIME_TYPES and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported content type '{mime}'")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    return data, filename, mime


def extract_text(data: bytes, filename: str, mime: str) -> tuple[str, int]:
    """Extract plain text from supported file bytes. Returns (text, page_count)."""
    ext = _ext(filename)
    text = ""
    page_count = 0
    try:
        if ext == ".pdf" or mime == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n\n".join(pages).strip()
            page_count = len(reader.pages)
        elif ext == ".docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            from docx import Document

            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs if p.text]
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
                    if row_text:
                        parts.append(" | ".join(row_text))
            text = "\n".join(parts).strip()
            page_count = max(1, len(doc.paragraphs) // 40) if doc.paragraphs else 1
        elif ext in {".txt", ".md"} or mime.startswith("text/") or mime == "application/octet-stream":
            try:
                text = data.decode("utf-8").strip()
            except UnicodeDecodeError:
                text = data.decode("latin-1", errors="ignore").strip()
            page_count = 1
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type for extraction")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not extract text from file: {str(exc)[:120]}")

    if not text:
        raise HTTPException(status_code=400, detail="No extractable text found in the uploaded file")
    return text, page_count
