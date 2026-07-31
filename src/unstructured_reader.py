"""unstructured-based PDF reader."""

from __future__ import annotations

from pathlib import Path

from src.utils import _ensure_native_tools_on_path, validate_pdf_path


class UnstructuredReader:
    """Reads text from PDFs using the unstructured library."""

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF and return its full text content.

        Args:
            file_path: Path to the PDF.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text, elements joined by blank lines.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        # unstructured depends on pdf2image (Poppler) and pytesseract at runtime
        _ensure_native_tools_on_path()

        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(str(path))
        return "\n\n".join([el.text for el in elements])
