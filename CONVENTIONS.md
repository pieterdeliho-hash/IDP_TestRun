# Project Conventions

## Naming

| Entity | Convention | Example |
|--------|-----------|---------|
| Modules (files) | `snake_case` | `document_reader.py` |
| Classes | `PascalCase` | `PDFReader` |
| Functions / methods | `snake_case` | `read()`, `_ocr_pages()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PAGES` |
| Private methods | leading underscore | `_ocr_pages()` |
| Variables | `snake_case` | `page_indices` |
| Type aliases | `PascalCase` | `PageResult` |

## Type Hints

- **Every** public function must have full type annotations (params + return).
- Use `|` for unions (Python 3.10+ syntax), not `Union` or `Optional`.
  ```python
  def read(self, file_path: str | Path, *, use_ocr: bool = True) -> str:
  ```
- Use `list[T]`, `dict[K, V]` — not `List`, `Dict` from `typing`.
- Add `from __future__ import annotations` at the top of every module.
- Return type `-> None` is required for `__init__` and void functions.
- Prefer `# type: ignore[...]` with a specific error code over a bare `str()` cast.

## Code Style

- **Keyword-only args** after `*` for optional/flag parameters:
  ```python
  def batch_read(directory, output_dir=None, *, use_ocr=True) -> dict[str, str]:
  ```
- **Imports:** standard library → third-party → local, each group separated by a blank line.
- **Docstrings:** triple-quoted, one-line summary + Args/Returns/Raises where applicable.
- **Line length:** 88 characters.
- **No unused imports, variables, or parameters** — mypy `warn_unreachable` catches dead code.
- **Common reader interface:** Every `*Reader` class implements `read(file_path: str | Path) -> str`.

## File Structure

```
src/
  __init__.py              # Public API re-exports
  document_reader.py       # PDFReader (pypdf + pytesseract OCR)
  pymupdf_reader.py        # PyMuPDFReader (fitz)
  pdfplumber_reader.py     # PdfPlumberReader
  docling_reader.py        # DoclingReader
  unstructured_reader.py   # UnstructuredReader
  hybrid_reader.py         # HybridReader (pymupdf → docling OCR fallback)
  surya_reader.py          # SuryaReader (pure ONNX OCR)
  marker_reader.py         # MarkerReader (markdown + layout)
  image_reader.py          # ImageReader (tesseract/surya/marker)
  benchmark.py             # Auto-discovers and compares all readers
  gui.py                   # CustomTkinter GUI (read, compare, batch, benchmark)
  utils.py                 # find_pdfs(), batch_read(), ReaderProtocol
tests/
  __init__.py
  test_document_reader.py
  test_benchmark.py
  test_hybrid_reader.py
  test_surya_reader.py
  test_marker_reader.py
  test_image_reader.py
  test_utils.py
  test_idp_benchmark.py
pyproject.toml             # mypy config (strict)
requirements.txt
CONVENTIONS.md
CLAUDE.md
README.md
```

## Testing

- Name test files `test_<module>.py`.
- Name test classes `Test<ClassName>`.
- Name test methods `test_<behavior>`.
- Use `pytest.fixture` for shared setup.