"""PyMuPDF-based PDF reader."""

from __future__ import annotations

from pathlib import Path

from src.utils import validate_pdf_path


class PyMuPDFReader:
    """Reads text from PDFs using PyMuPDF (fitz)."""

    def read(self, file_path: str | Path) -> str:
        """Read a PDF and return its full text content.

        Args:
            file_path: Path to the PDF.

        Returns:
            The extracted text, pages separated by blank lines.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        import fitz  # PyMuPDF

        with fitz.open(str(path)) as doc:
            pages: list[str] = []
            for page in doc:
                text = page.get_text("text")
                pages.append(text)
        return "\n\n".join(pages)
