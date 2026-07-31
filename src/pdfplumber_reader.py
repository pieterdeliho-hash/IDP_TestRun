"""pdfplumber-based PDF reader."""

from __future__ import annotations

from pathlib import Path

from src.utils import validate_pdf_path


class PdfPlumberReader:
    """Reads text from PDFs using pdfplumber."""

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF and return its full text content.

        Args:
            file_path: Path to the PDF.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text, pages separated by blank lines.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return "\n\n".join(pages)
