"""Image reader supporting multiple OCR backends."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils import (
    _ensure_native_tools_on_path,
    _marker_config_kwargs,
    validate_doc_path,
)


class ImageReader:
    """Reads text from images using configurable OCR backend.

    Supports JPEG, PNG, TIFF, and BMP formats.
    """

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}

    def __init__(self, *, backend: str = "tesseract") -> None:
        """Initialize the image reader.

        Args:
            backend: OCR engine to use ("tesseract", "surya", "marker").
        """
        self._backend = backend

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read an image and return its OCR text.

        Args:
            file_path: Path to the image file.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a supported image format.
        """
        path = validate_doc_path(file_path, self.SUPPORTED_EXTENSIONS)

        if self._backend == "tesseract":
            return self._read_tesseract(path)
        elif self._backend == "surya":
            return self._read_surya(path)
        elif self._backend == "marker":
            return self._read_marker(path)
        else:
            raise ValueError(f"Unknown backend: {self._backend}")

    def _read_tesseract(self, path: Path) -> str:
        """Extract text using Tesseract OCR."""
        _ensure_native_tools_on_path()

        import pytesseract  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        with Image.open(str(path)) as img:
            text = pytesseract.image_to_string(img)
        return text.strip()  # type: ignore[no-any-return]

    def _read_surya(self, path: Path) -> str:
        """Extract text using Surya OCR."""
        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from PIL import Image  # noqa: PLC0415
        from surya.inference import SuryaInferenceManager  # noqa: PLC0415
        from surya.recognition import RecognitionPredictor  # noqa: PLC0415

        with Image.open(str(path)) as img:
            manager = SuryaInferenceManager()
            predictor = RecognitionPredictor(manager)
            page_results = predictor([img], full_page=True)

        lines: list[str] = []
        for result in page_results:
            for line in result.lines:
                lines.append(line.text)
        return "\n".join(lines)

    def _read_marker(self, path: Path) -> str:
        """Extract text using Marker OCR."""
        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from PIL import Image  # noqa: PLC0415
        from marker.config.parser import ConfigParser  # noqa: PLC0415
        from marker.converters.pdf import PdfConverter  # noqa: PLC0415
        from marker.models import create_model_dict  # noqa: PLC0415

        # Marker works on PDFs, so convert image to single-page PDF first
        import fitz  # noqa: PLC0415

        doc = fitz.open()
        with Image.open(str(path)) as img:
            img_bytes = img.tobytes()
            if img.mode == "RGBA":
                img = img.convert("RGB")  # type: ignore[assignment]
                img_bytes = img.tobytes()
            width, height = img.size
            doc.insert_image([0, 0, width, height], pixels=img_bytes, dpi=72)

        # Write temp PDF
        import tempfile  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name

        try:
            models = create_model_dict()
            config_parser = ConfigParser(_marker_config_kwargs())
            config_dict = config_parser.generate_config_dict()

            converter = PdfConverter(
                config=config_dict,
                artifact_dict=models,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
            )
            rendered = converter(tmp_path)
            return rendered.text if hasattr(rendered, "text") else str(rendered)
        finally:
            os.unlink(tmp_path)
