"""Docling-based PDF reader."""

from __future__ import annotations

from pathlib import Path

from src.utils import validate_pdf_path


class DoclingReader:
    """Reads text from PDFs using the Docling document converter."""

    _converter: object | None = None

    def read(self, file_path: str | Path) -> str:
        """Read a PDF and return its full text as markdown.

        Args:
            file_path: Path to the PDF.

        Returns:
            The extracted text (markdown format).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        from docling.document_converter import DocumentConverter

        if DoclingReader._converter is None:
            DoclingReader._converter = DocumentConverter()

        result = DoclingReader._converter.convert(str(path))  # type: ignore[attr-defined]
        return result.document.export_to_markdown()  # type: ignore[no-any-return]
