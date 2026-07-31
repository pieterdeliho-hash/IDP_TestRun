"""Hybrid PDF reader: pymupdf for speed, docling for accuracy.

Strategy:
    1. Extract with pymupdf (instant for text-layer PDFs)
    2. If chars_per_page < threshold, re-extract with docling (OCR + layout aware)
    3. Log the actual chars_per_page so the threshold can be tuned
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.utils import _get_docling_converter, validate_pdf_path

logger = logging.getLogger(__name__)


class HybridReader:
    """Reads PDFs using pymupdf first, falling back to docling for scanned/complex PDFs."""

    def __init__(self, *, fallback_chars_per_page: int = 50) -> None:
        """Initialize the hybrid reader.

        Args:
            fallback_chars_per_page: Characters-per-page below which docling is
                                     used instead of pymupdf output.
        """
        self._fallback_chars_per_page = fallback_chars_per_page

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF using the hybrid approach.

        Args:
            file_path: Path to the PDF.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text from the best-suited reader.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        # ── Pass 1: pymupdf (fast native extraction) ────────────────
        import fitz  # noqa: PLC0415

        doc = fitz.open(str(path))
        page_texts: list[str] = []
        for page in doc:
            page_texts.append(page.get_text("text"))
        doc.close()

        page_count = len(page_texts)
        total_chars = sum(len(t) for t in page_texts)
        chars_per_page = total_chars / page_count if page_count > 0 else 0

        logger.info(
            "Hybrid pass1 (%s): %d pages, %d chars, %.1f chars/page",
            path.name,
            page_count,
            total_chars,
            chars_per_page,
        )

        if chars_per_page >= self._fallback_chars_per_page:
            return "".join(page_texts)

        # ── Pass 2: docling (OCR + layout aware) ────────────────────
        logger.info(
            "Hybrid pass2 (%s): chars_per_page %.1f < %d, falling back to docling",
            path.name,
            chars_per_page,
            self._fallback_chars_per_page,
        )

        import os  # noqa: PLC0415

        from src.utils import _ensure_native_tools_on_path

        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        converter = _get_docling_converter()
        result = converter.convert(str(path))  # type: ignore[attr-defined]
        return result.document.export_to_markdown()  # type: ignore[no-any-return]
