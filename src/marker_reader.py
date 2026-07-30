"""Marker PDF reader — Surya OCR + layout detection + table extraction."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils import _ensure_native_tools_on_path, validate_pdf_path


class MarkerReader:
    """Reads text from PDFs using Marker (S Surya + layout + tables).

    Marker combines Surya OCR with layout detection and table extraction,
    purpose-built for invoices, receipts, and structured documents.
    """

    def read(self, file_path: str | Path) -> str:
        """Read a PDF and return its full text content via Marker.

        Args:
            file_path: Path to the PDF.

        Returns:
            The extracted text as markdown.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not a PDF.
        """
        path = validate_pdf_path(file_path)

        _ensure_native_tools_on_path()
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        from marker.config.parser import ConfigParser  # type: ignore[import-untyped]  # noqa: PLC0415
        from marker.converters.pdf import PdfConverter  # type: ignore[import-untyped]  # noqa: PLC0415
        from marker.models import create_model_dict  # type: ignore[import-untyped]  # noqa: PLC0415

        # Load models
        models = create_model_dict()

        # Build config — markdown renderer, no LLM
        config_kwargs = {
            "output_format": "markdown",
            "output_folder": None,
            "langs": None,
            "chunk_num": None,
            "start_page": None,
            "end_page": None,
            "infer_format": False,
            "infer_layout_format": False,
            "force_gpu": 0,
            "page_cache": None,
            "workers": None,
            "batch_multiplier": 1,
            "disable_image_download": False,
            "increase_resolution": False,
            "crop_bboxes": None,
            "renderer": "markdown",
            "processors": None,
            "llm_service": None,
            "llm_service_config": None,
            "high_table_noise": False,
            "pdf_dpi": None,
            "table_rec": False,
            "equation_to_svg": False,
            "equation_to_svg_chunk_memory": False,
            "chat_client": None,
            "chat_model": None,
            "chat_model_api": None,
            "handwriting": False,
            "debug": False,
            "output_schema": False,
            "infer_line_groups": False,
            "page_range": None,
        }
        config_parser = ConfigParser(config_kwargs)
        config_dict = config_parser.generate_config_dict()

        converter = PdfConverter(
            config=config_dict,
            artifact_dict=models,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
        )

        rendered = converter(str(path))
        return rendered.text if hasattr(rendered, "text") else str(rendered)
