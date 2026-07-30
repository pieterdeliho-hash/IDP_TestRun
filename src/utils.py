"""Shared utilities for document processing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class ReaderProtocol(Protocol):
    """Protocol shared by all document reader classes."""

    def read(self, file_path: str | Path) -> str: ...


# ── Supported formats ────────────────────────────────────────────────

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
ALL_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS


# ── Auto-detect Poppler / Tesseract on Windows ──────────────────────


def _ensure_native_tools_on_path() -> None:
    """Prepend Poppler and Tesseract directories to PATH if missing.

    Both ``pdf2image`` (Poppler) and ``pytesseract`` need their
    executables on PATH at runtime.  This helper auto-detects common
    install locations so the user doesn't have to set PATH manually.
    """
    candidates: list[str] = [
        # Poppler — Git for Windows
        r"C:\Program Files\Git\mingw64\bin",
        r"C:\Program Files\Git\usr\bin",
        # Tesseract — winget default
        r"C:\Program Files\Tesseract-OCR",
    ]

    # Poppler — winget (oschwartz10612), version-agnostic
    base = Path(r"C:\Users\Pieter\AppData\Local\Microsoft\WinGet\Packages")
    if base.is_dir():
        for pkg in base.iterdir():
            if not pkg.name.startswith("oschwartz10612.Poppler"):
                continue
            for folder in pkg.iterdir():
                bin_dir = folder / "Library" / "bin"
                if bin_dir.is_dir():
                    candidates.append(str(bin_dir))

    current = os.environ.get("PATH", "")
    for d in candidates:
        if os.path.isdir(d) and d not in current:
            current = d + os.pathsep + current
    os.environ["PATH"] = current


# ── Path validation ─────────────────────────────────────────────────


def validate_pdf_path(file_path: str | Path) -> Path:
    """Validate that *file_path* exists and is a PDF.

    Args:
        file_path: Path to validate.

    Returns:
        A resolved :class:`Path` object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the file extension is not ``.pdf``.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a .pdf file, got '{path.suffix}'. "
            f"File: {path.name}"
        )

    return path


def validate_doc_path(
    file_path: str | Path, extensions: set[str]
) -> Path:
    """Validate that *file_path* exists and has a supported extension.

    Args:
        file_path:  Path to validate.
        extensions: Set of allowed extensions (lowercase, with dot).

    Returns:
        A resolved :class:`Path` object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the file extension is not supported.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in extensions:
        raise ValueError(
            f"Unsupported extension '{path.suffix}'. "
            f"Supported: {', '.join(sorted(extensions))}. "
            f"File: {path.name}"
        )

    return path


# ── File discovery ──────────────────────────────────────────────────


def find_pdfs(
    directory: str | Path, *, recursive: bool = True
) -> list[Path]:
    """Find all PDF files in a directory (case-insensitive).

    Args:
        directory: Path to search.
        recursive: Include subdirectories.

    Returns:
        Sorted list of PDF file paths.
    """
    return find_documents(directory, PDF_EXTENSIONS, recursive=recursive)


def find_documents(
    directory: str | Path,
    extensions: set[str] | None = None,
    *,
    recursive: bool = True,
) -> list[Path]:
    """Find all supported document files in a directory.

    Args:
        directory: Path to search.
        extensions: Set of extensions to match. Defaults to all supported.
        recursive: Include subdirectories.

    Returns:
        Sorted list of file paths.
    """
    if extensions is None:
        extensions = ALL_EXTENSIONS

    dir_path = Path(directory)
    patterns = [f"*{ext}" for ext in extensions]
    if recursive:
        patterns = [f"**/*{ext}" for ext in extensions]

    found: set[Path] = set()
    for pattern in patterns:
        found.update(dir_path.glob(pattern))
    return sorted(found, key=lambda p: p.name)


# ── Batch read ───────────────────────────────────────────────────────


def batch_read(
    directory: str | Path,
    output_dir: str | Path | None = None,
    *,
    use_ocr: bool = True,
    tesseract_cmd: str | None = None,
) -> dict[str, str]:
    """Read every PDF in a directory.

    Args:
        directory:   Folder containing PDFs.
        output_dir:  If set, write one .txt per PDF here.
        use_ocr:     Enable OCR fallback for scanned pages.
        tesseract_cmd: Path to tesseract executable (optional).

    Returns:
        Dict mapping PDF filenames to extracted text.
    """
    import sys  # noqa: PLC0415

    from src.document_reader import PDFReader

    reader = PDFReader(tesseract_cmd=tesseract_cmd)
    results: dict[str, str] = {}
    errors = 0

    pdfs = find_pdfs(directory)
    for pdf in pdfs:
        try:
            text = reader.read(pdf, use_ocr=use_ocr)
            results[pdf.name] = text

            if output_dir:
                out = Path(output_dir) / f"{pdf.stem}.txt"
                out.write_text(text, encoding="utf-8")
        except Exception as e:
            results[pdf.name] = f"ERROR: {e}"
            errors += 1
            print(
                f"  WARNING: failed to read {pdf.name}: {e}",
                file=sys.stderr,
            )

    if errors:
        print(
            f"  {errors}/{len(pdfs)} file(s) failed.",
            file=sys.stderr,
        )

    return results
