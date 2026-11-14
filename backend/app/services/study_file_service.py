"""Helpers for extracting text from uploaded study material files."""

import base64
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
    canonical_mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }
    if ext in canonical_mime:
        mime = canonical_mime[ext]
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    return data, filename, mime


def get_pdf_page_count(data: bytes) -> int:
    """Return the number of pages in a readable, unencrypted PDF."""
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
        if document.needs_pass:
            document.close()
            raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported")
        page_count = len(document)
        document.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(exc)[:120]}")
    if page_count < 1:
        raise HTTPException(status_code=400, detail="PDF contains no pages")
    return page_count


def render_pdf_pages(
    data: bytes,
    page_numbers: list[int] | None = None,
    max_dimension: int = 960,
) -> list[dict]:
    """Render selected PDF pages as bounded PNG data URLs for the reader."""
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
        if document.needs_pass:
            document.close()
            raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported")
        total_pages = len(document)
        numbers = page_numbers or list(range(1, total_pages + 1))
        if any(page < 1 or page > total_pages for page in numbers):
            raise HTTPException(status_code=400, detail="Requested page is outside the document")

        pages = []
        for number in numbers:
            page = document[number - 1]
            rect = page.rect
            scale = min(max_dimension / max(rect.width, rect.height), 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append({
                "page": number,
                "image_url": f"data:image/png;base64,{image}",
                "width": pixmap.width,
                "height": pixmap.height,
                "is_scan": not bool(page.get_text("text").strip()),
            })
        document.close()
        return pages
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not render PDF pages: {str(exc)[:120]}")


def extract_pdf_figures(data: bytes) -> list[dict]:
    """Extract embedded PDF images as figure data URLs."""
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
        figures = []
        seen_on_page: set[tuple[int, int]] = set()
        for page_number, page in enumerate(document, start=1):
            for image in page.get_images(full=True):
                xref = image[0]
                key = (page_number, xref)
                if key in seen_on_page:
                    continue
                seen_on_page.add(key)
                pixmap = fitz.Pixmap(document, xref)
                if pixmap.n - pixmap.alpha >= 4:
                    pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                image_bytes = pixmap.tobytes("png")
                figures.append({
                    "figure_index": len(figures),
                    "page": page_number,
                    "image_url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}",
                    "width": pixmap.width,
                    "height": pixmap.height,
                    "description": None,
                    "caption": None,
                })
        document.close()
        return figures
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not extract PDF figures: {str(exc)[:120]}")


def render_image_page(data: bytes, mime: str, max_dimension: int = 960) -> list[dict]:
    """Return one bounded preview page for a stored image material."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as source:
            source.load()
            width, height = source.size
            scale = min(max_dimension / max(width, height), 1)
            if scale < 1:
                source.thumbnail((int(width * scale), int(height * scale)))
                output = io.BytesIO()
                source.convert("RGB").save(output, format="PNG")
                data = output.getvalue()
                mime = "image/png"
                width, height = source.size
        image = base64.b64encode(data).decode("ascii")
        return [{
            "page": 1,
            "image_url": f"data:{mime};base64,{image}",
            "width": width,
            "height": height,
            "is_scan": True,
        }]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not render image: {str(exc)[:120]}")


def images_to_pdf(images: list[tuple[bytes, str]]) -> bytes:
    """Package uploaded page images into a PDF so the complete source is retained."""
    try:
        import fitz
        from PIL import Image

        document = fitz.open()
        for image_bytes, _ in images:
            with Image.open(io.BytesIO(image_bytes)) as source:
                source.load()
                width, height = source.size
                if width < 1 or height < 1:
                    raise ValueError("Image has invalid dimensions")
                output = io.BytesIO()
                source.convert("RGB").save(output, format="PNG")
            page = document.new_page(width=612, height=792)
            page.insert_image(page.rect, stream=output.getvalue(), keep_proportion=True)
        result = document.tobytes()
        document.close()
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not prepare uploaded images: {str(exc)[:120]}")


def extract_text(
    data: bytes,
    filename: str,
    mime: str,
    selected_pages: list[int] | None = None,
) -> tuple[str, int]:
    """Extract plain text from supported file bytes. Returns (text, page_count)."""
    ext = _ext(filename)
    text = ""
    page_count = 0
    try:
        if ext == ".pdf" or mime == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            page_count = len(reader.pages)
            if selected_pages is not None:
                if not selected_pages:
                    raise HTTPException(status_code=400, detail="Select at least one PDF page")
                if len(set(selected_pages)) != len(selected_pages):
                    raise HTTPException(status_code=400, detail="PDF page selection contains duplicates")
                if any(page < 1 or page > page_count for page in selected_pages):
                    raise HTTPException(status_code=400, detail="Selected page is outside the document")
                pages_to_read = [reader.pages[page - 1] for page in sorted(selected_pages)]
            else:
                pages_to_read = reader.pages
            pages = []
            for page in pages_to_read:
                pages.append(page.extract_text() or "")
            text = "\n\n".join(pages).strip()
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
