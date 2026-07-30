"""Surya OCR-based PDF reader."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils import _ensure_native_tools_on_path, validate_pdf_path


class SuryaReader:
    """Reads text from PDFs using Surya OCR engine.

    Surya is a modern open-source OCR with multilingual support,
    word-level bounding boxes, and layout-aware text extraction.
    """

    def read(self, file_path: str | Path) -> str:
        """Read a PDF and return its full text content via Surya OCR.

        Args:
            file_path: Path to the PDF.

        Returns:
            The extracted text.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from PIL import Image  # noqa: PLC0415
        import fitz  # noqa: PLC0415

        from surya.recognition import RecognitionPredictor  # type: ignore[import-untyped]  # noqa: PLC0415

        # Convert PDF pages to high-res images
        doc = fitz.open(str(path))
        images: list[Image.Image] = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)
        doc.close()

        # Run Surya OCR — manager=None uses pure ONNX models (no Docker/LLM needed)
        predictor = RecognitionPredictor(manager=None)
        page_results = predictor(images, full_page=True)

        # Extract text from results
        lines: list[str] = []
        for result in page_results:
            for line in result.lines:
                lines.append(line.text)

        return "\n".join(lines)
