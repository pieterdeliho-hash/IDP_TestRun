# CLAUDE.md

Project-specific instructions for Claude Code working in this repository.

## Project Overview

PDF reader for extracting text from both native-text and scanned (OCR) PDFs.
Five backends: PyPDF+OCR, PyMuPDF, pdfplumber, Docling, unstructured.
Benchmark tool compares all installed readers on speed and output quality.
Python 3.11+, strict typing via mypy.

## Key Rules

- **Strict types always.** Every function gets full annotations. Use `|` unions, `list[T]`, `dict[K, V]`, and `from __future__ import annotations`.
- **Follow `CONVENTIONS.md`** for naming, style, and structure.
- **`src/`** holds production code. **`tests/`** holds tests. Nothing else.
- **Keyword-only args** (`*`) for optional/flag parameters.
- **No unused imports, variables, or parameters.**
- **All readers share the same interface:** `read(file_path: str | Path) -> str`
- **Run mypy** after any code change: `mypy src/`
- **Run tests** after any code change: `pytest tests/ -v`

## Dependencies

- `pypdf` — native PDF text extraction
- `pytesseract` + `pdf2image` + `Pillow` — OCR for scanned pages
- `PyMuPDF` — fast C-based extraction (fitz)
- `pdfplumber` — layout-aware extraction
- `docling` — AI-based structured extraction
- `unstructured` — entity-aware extraction
- `mypy` — strict type checking
- `pytest` — testing

## Tesseract

OCR requires [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) installed on the system.
On Windows, pass the path via `PDFReader(tesseract_cmd=...)` if not on PATH.

## Benchmark

```powershell
python -m src.benchmark path/to/file.pdf
python -m src.benchmark --batch path/to/pdfs
python -m src.benchmark file.pdf --methods pypdf+ocr pymupdf
```