"""Docling-based PDF reader."""

from __future__ import annotations

from pathlib import Path

from src.utils import _get_docling_converter, validate_pdf_path


class DoclingReader:
    """Reads text from PDFs using the Docling document converter."""

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF and return its full text as markdown.

        Args:
            file_path: Path to the PDF.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text (markdown format).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        converter = _get_docling_converter()
        result = converter.convert(str(path))  # type: ignore[attr-defined]
        return result.document.export_to_markdown()  # type: ignore[no-any-return]
