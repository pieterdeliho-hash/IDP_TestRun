"""Reader registry — discovers available readers and creates adapters.

Adapters wrap the existing ``src/`` reader classes so they conform to
the :class:`BenchReader` interface.  This way no extraction logic is
duplicated; we only add timing, memory, and result-persistence layers.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from idp_benchmark.readers.base import BenchReader

logger = logging.getLogger(__name__)


# ── Registry: maps reader name -> module + class ─────────────────────

_READERS: dict[str, dict[str, Any]] = {
    "pypdf+ocr": {
        "module": "src.document_reader",
        "class": "PDFReader",
        "formats": ["pdf"],
    },
    "pymupdf": {
        "module": "src.pymupdf_reader",
        "class": "PyMuPDFReader",
        "formats": ["pdf"],
    },
    "pdfplumber": {
        "module": "src.pdfplumber_reader",
        "class": "PdfPlumberReader",
        "formats": ["pdf"],
    },
    "docling": {
        "module": "src.docling_reader",
        "class": "DoclingReader",
        "formats": ["pdf"],
    },
    "unstructured": {
        "module": "src.unstructured_reader",
        "class": "UnstructuredReader",
        "formats": ["pdf"],
    },
    "hybrid": {
        "module": "src.hybrid_reader",
        "class": "HybridReader",
        "formats": ["pdf"],
    },
    "marker": {
        "module": "src.marker_reader",
        "class": "MarkerReader",
        "formats": ["pdf"],
    },
    "surya": {
        "module": "src.surya_reader",
        "class": "SuryaReader",
        "formats": ["pdf"],
    },
    "image+tesseract": {
        "module": "src.image_reader",
        "class": "ImageReader",
        "formats": ["image"],
        "args": {"backend": "tesseract"},
    },
}

# Package discovery map — used to check if a reader is installed
_PKG_MAP: dict[str, list[str]] = {
    "pypdf+ocr": ["pypdf"],
    "pymupdf": ["fitz"],
    "pdfplumber": ["pdfplumber"],
    "docling": ["docling"],
    "unstructured": ["unstructured"],
    "hybrid": ["fitz", "docling"],
    "marker": ["marker"],
    "surya": ["surya"],
    "image+tesseract": ["pytesseract"],
}


# ── Adapter: wraps any src/ reader as a BenchReader ──────────────────


class _Adapter(BenchReader):
    """Thin BenchReader adapter around an existing src/ reader class."""

    def __init__(
        self,
        name: str,
        reader_instance: Any,
        *,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name, config=config)
        self._reader = reader_instance

    def extract(self, file_path: str | Path) -> str:
        return self._reader.read(file_path)  # type: ignore[no-any-return]


# ── Public API ───────────────────────────────────────────────────────


def register_reader(
    name: str,
    *,
    module: str,
    cls: str,
    formats: list[str] | None = None,
    pkg_check: list[str] | None = None,
    args: dict[str, Any] | None = None,
) -> None:
    """Register a new reader in the framework.

    Args:
        name:        Short identifier (e.g. ``"paddleocr"``).
        module:      Dotted module path containing the reader class.
        cls:         Reader class name.
        formats:     Supported formats (``["pdf"]``, ``["image"]``).
        pkg_check:   Package names whose importability indicates availability.
        args:        Default constructor arguments.
    """
    _READERS[name] = {
        "module": module,
        "class": cls,
        "formats": formats or ["pdf"],
        "args": args or {},
    }
    if pkg_check:
        _PKG_MAP[name] = pkg_check


def discover_readers(
    *,
    file_format: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return only the readers whose packages are installed.

    Args:
        file_format: If set, only return readers for this format.

    Returns:
        Dict of reader_name -> configuration dict.
    """
    available: dict[str, dict[str, Any]] = {}
    for name, cfg in _READERS.items():
        if file_format and file_format not in cfg.get("formats", []):
            continue
        pkgs = _PKG_MAP.get(name, [cfg["module"].split(".")[0]])
        try:
            for pkg in pkgs:
                importlib.import_module(pkg)
            available[name] = cfg
        except ImportError:
            logger.debug("Skipping %s: dependency not installed", name)
    return available


def create_bench_reader(
    name: str,
    *,
    tesseract_cmd: str | None = None,
    config: dict[str, Any] | None = None,
) -> BenchReader:
    """Instantiate a ``BenchReader`` adapter for the given reader name.

    Args:
        name:          Reader identifier (e.g. ``"pymupdf"``).
        tesseract_cmd: Path to tesseract executable (for OCR readers).
        config:        Extra configuration forwarded to the adapter.

    Returns:
        A :class:`BenchReader` instance wrapping the underlying reader.

    Raises:
        KeyError: If *name* is not registered.
    """
    cfg = _READERS[name]
    mod = importlib.import_module(cfg["module"])
    cls = getattr(mod, cfg["class"])
    args = cfg.get("args", {})

    if name == "pypdf+ocr":
        reader_instance = cls(tesseract_cmd=tesseract_cmd, **args)
    else:
        reader_instance = cls(**args)

    return _Adapter(name, reader_instance, config=config)
