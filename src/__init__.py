"""Document reader package — supports PDFs and images via multiple backends.

All reader classes and utilities are lazily imported on first access so that
heavy dependencies (docling, unstructured) are not loaded unless needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.docling_reader import DoclingReader
    from src.document_reader import PDFReader
    from src.hybrid_reader import HybridReader
    from src.image_reader import ImageReader
    from src.marker_reader import MarkerReader
    from src.pdfplumber_reader import PdfPlumberReader
    from src.pymupdf_reader import PyMuPDFReader
    from src.surya_reader import SuryaReader
    from src.unstructured_reader import UnstructuredReader
    from src.utils import (
        ReaderProtocol,
        batch_read,
        find_documents,
        find_pdfs,
        validate_doc_path,
        validate_pdf_path,
    )


def __getattr__(name: str) -> object:
    """Lazy-import public symbols on first access."""
    import importlib  # noqa: PLC0415

    _registry: dict[str, tuple[str, str]] = {
        "PDFReader": ("src.document_reader", "PDFReader"),
        "PyMuPDFReader": ("src.pymupdf_reader", "PyMuPDFReader"),
        "PdfPlumberReader": ("src.pdfplumber_reader", "PdfPlumberReader"),
        "DoclingReader": ("src.docling_reader", "DoclingReader"),
        "UnstructuredReader": ("src.unstructured_reader", "UnstructuredReader"),
        "HybridReader": ("src.hybrid_reader", "HybridReader"),
        "SuryaReader": ("src.surya_reader", "SuryaReader"),
        "MarkerReader": ("src.marker_reader", "MarkerReader"),
        "ImageReader": ("src.image_reader", "ImageReader"),
        "ReaderProtocol": ("src.utils", "ReaderProtocol"),
        "batch_read": ("src.utils", "batch_read"),
        "find_pdfs": ("src.utils", "find_pdfs"),
        "find_documents": ("src.utils", "find_documents"),
        "validate_pdf_path": ("src.utils", "validate_pdf_path"),
        "validate_doc_path": ("src.utils", "validate_doc_path"),
    }

    if name not in _registry:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    mod_path, attr = _registry[name]
    mod = importlib.import_module(mod_path)
    val = getattr(mod, attr)

    import sys  # noqa: PLC0415

    sys.modules[__name__].__dict__[name] = val
    return val


__all__ = [
    "DoclingReader",
    "HybridReader",
    "ImageReader",
    "MarkerReader",
    "PdfPlumberReader",
    "PDFReader",
    "PyMuPDFReader",
    "ReaderProtocol",
    "SuryaReader",
    "UnstructuredReader",
    "batch_read",
    "find_documents",
    "find_pdfs",
    "validate_doc_path",
    "validate_pdf_path",
]
