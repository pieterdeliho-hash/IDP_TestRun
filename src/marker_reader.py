"""Marker PDF reader — Surya OCR + layout detection + table extraction."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils import _ensure_native_tools_on_path, _marker_config_kwargs, validate_pdf_path


class MarkerReader:
    """Reads text from PDFs using Marker (S Surya + layout + tables).

    Marker combines Surya OCR with layout detection and table extraction,
    purpose-built for invoices, receipts, and structured documents.
    """

    _models: object | None = None

    def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
        """Read a PDF and return its full text content via Marker.

        Args:
            file_path: Path to the PDF.
            use_ocr:   Reserved for protocol compatibility (unused here).

        Returns:
            The extracted text as markdown.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from marker.config.parser import ConfigParser  # noqa: PLC0415
        from marker.converters.pdf import PdfConverter  # noqa: PLC0415
        from marker.models import create_model_dict  # noqa: PLC0415

        # Load models (cached)
        if MarkerReader._models is None:
            MarkerReader._models = create_model_dict()

        config_parser = ConfigParser(_marker_config_kwargs())
        config_dict = config_parser.generate_config_dict()

        converter = PdfConverter(
            config=config_dict,
            artifact_dict=MarkerReader._models,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
        )

        rendered = converter(str(path))
        return rendered.text if hasattr(rendered, "text") else str(rendered)
