"""Hybrid PDF reader: pymupdf for speed, docling for accuracy."""

from __future__ import annotations

from pathlib import Path

from src.utils import validate_pdf_path


class HybridReader:
    """Reads PDFs using pymupdf first, falling back to docling for scanned/complex PDFs.

    Strategy:
        1. Extract with pymupdf (instant for text-layer PDFs)
        2. If chars < threshold, re-extract with docling (OCR + layout aware)
    """

    def __init__(self, *, fallback_threshold: int = 100) -> None:
        """Initialize the hybrid reader.

        Args:
            fallback_threshold: Character count below which docling is used
                               instead of pymupdf output.
        """
        self._fallback_threshold = fallback_threshold

    def read(self, file_path: str | Path) -> str:
        """Read a PDF using the hybrid approach.

        Args:
            file_path: Path to the PDF.

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
        pymupdf_text = "".join(page.get_text() for page in doc)
        doc.close()

        if len(pymupdf_text) >= self._fallback_threshold:
            return pymupdf_text

        # ── Pass 2: docling (OCR + layout aware) ────────────────────
        import os  # noqa: PLC0415

        from src.utils import _ensure_native_tools_on_path

        _ensure_native_tools_on_path()

        # Suppress huggingface symlinks warning on Windows
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        return result.document.export_to_markdown()
