"""Text extraction from PDF/image documents (Phase 5).

PDF parsing via pdfplumber is mandatory. Image OCR via pytesseract is optional
and cuttable — if the tesseract binary is unavailable, extract_text returns ""
gracefully rather than raising. extract_text NEVER raises.
"""

import io

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif")


def _looks_like_pdf(file_bytes: bytes) -> bool:
    return bool(file_bytes) and file_bytes[:5].startswith(b"%PDF")


def _extract_pdf(file_bytes: bytes) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
    return "\n".join(parts)


def _extract_image(file_bytes: bytes) -> str:
    import pytesseract
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from a PDF or image. Returns "" on any failure (never raises)."""
    if not file_bytes:
        return ""

    name = (filename or "").lower()
    is_pdf = name.endswith(".pdf") or _looks_like_pdf(file_bytes)

    try:
        if is_pdf:
            return _extract_pdf(file_bytes) or ""
        # Image path (or unknown non-PDF): OCR is optional/cuttable.
        return _extract_image(file_bytes) or ""
    except Exception:
        # Includes pytesseract.TesseractNotFoundError, PIL errors, corrupt PDFs.
        return ""
