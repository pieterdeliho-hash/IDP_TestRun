"""PDF reader supporting both text-based and scanned (OCR) documents."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils import _ensure_native_tools_on_path, validate_pdf_path


class PDFReader:
    """Reads text from PDF files, falling back to OCR for scanned pages."""

    def __init__(
        self,
        tesseract_cmd: str | None = None,
        *,
        ocr_lang: str = "eng",
    ) -> None:
        """Initialize the PDF reader.

        Args:
            tesseract_cmd: Path to the tesseract executable.
                           Auto-detected on most systems; set this if
                           the installer didn't add it to PATH.
            ocr_lang:      Tesseract language code (default ``"eng"``).
        """
        self._tesseract_cmd = tesseract_cmd
        self._ocr_lang = ocr_lang

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF and return its full text content.

        Args:
            file_path: Path to the PDF.
            use_ocr:   If True (default), run OCR on any page where
                       normal text extraction returned nothing
                       (scanned / image-only pages).

        Returns:
            The extracted text, one section per page separated by blank lines.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        # ── Pass 1: extract native text ────────────────────────────
        from pypdf import PdfReader

        pdf = PdfReader(str(path))

        pages: list[str] = []
        ocr_indices: list[int] = []

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
            elif use_ocr:
                ocr_indices.append(i)
                pages.append("")  # placeholder, filled by OCR below
            else:
                pages.append("")

        # ── Pass 2: OCR on empty (scanned) pages ───────────────────
        if ocr_indices:
            _ensure_native_tools_on_path()
            ocr_text = self._ocr_pages(path, ocr_indices)
            for idx, text in zip(ocr_indices, ocr_text):
                pages[idx] = text

        return "\n\n".join(pages)

    def _ocr_pages(
        self, pdf_path: Path, page_indices: list[int]
    ) -> list[str]:
        """Run OCR on specific pages of a PDF.

        Pages are 0-based indices.  Returns one string per index.
        """
        import pytesseract  # noqa: PLC0415
        from pdf2image import convert_from_path  # noqa: PLC0415

        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd

        results: dict[int, str] = {}

        # Convert only the needed pages (1-based for pdf2image)
        page_numbers = [i + 1 for i in page_indices]
        thread_count = os.cpu_count() or 4
        images = convert_from_path(
            str(pdf_path),
            first_page=min(page_numbers),
            last_page=max(page_numbers),
            thread_count=thread_count,
        )

        for i, img in enumerate(images):
            idx = page_indices[i]
            text = pytesseract.image_to_string(img, lang=self._ocr_lang)
            results[idx] = text.strip()

        return [results.get(i, "") for i in page_indices]
