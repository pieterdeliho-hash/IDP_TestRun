# Document Reader Benchmark

Extract text from PDFs and images using multiple backends — benchmark, compare, and pick the right reader for your use case.

Covers **native-text PDFs**, **scanned PDFs (OCR)**, and **image files** (JPEG, PNG, TIFF, BMP).

---

## Quick Start

```powershell
# Install dependencies
pip install -r requirements.txt

# Type check + test
mypy src/
pytest tests/ -v

# Benchmark a single file
python -m src.benchmark invoice.pdf

# Benchmark a directory
python -m src.benchmark --batch path/to/pdfs

# Run only specific methods
python -m src.benchmark invoice.pdf --methods pymupdf hybrid
```

---

## Prerequisites

### Python 3.11+

```powershell
python --version
```

### Tesseract OCR

Required for scanned PDF pages and image OCR.

```powershell
winget install UB-Mannheim.TesseractOCR
```

### Poppler

Required by `pdf2image` to render PDF pages as images.

```powershell
winget install Poppler
```

> **Note:** On Windows, both tools are auto-detected by the benchmark at common install paths (winget defaults, Git for Windows). No manual PATH configuration needed.

---

## Readers

| Reader | Package | Format | Best for |
|--------|---------|--------|----------|
| `PDFReader` | pypdf + pytesseract | PDF | Mixed text/scanned, auto-OCR fallback |
| `PyMuPDFReader` | PyMuPDF (fitz) | PDF | Speed — C-based, near-instant extraction |
| `PdfPlumberReader` | pdfplumber | PDF | Layout-aware text, tables |
| `DoclingReader` | docling | PDF | Complex layouts, AI-based extraction |
| `UnstructuredReader` | unstructured | PDF | Entity-aware extraction, ML pipelines |
| `HybridReader` | pymupdf + docling | PDF | **Best overall** — pymupdf speed + docling OCR fallback |
| `SuryaReader` | surya-ocr | PDF | Multilingual OCR, word-level bounding boxes |
| `MarkerReader` | marker-pdf | PDF | Markdown output, tables, layout detection |
| `ImageReader` | pytesseract/surya/marker | Image | JPEG, PNG, TIFF, BMP with configurable backend |

> **Note:** Surya and Marker require `transformers>=5.x` and `Pillow<11`, which conflicts with docling (`transformers<5`) and pdfplumber (`Pillow>=12.2`). They need a separate virtual environment. See `src/benchmark.py` for details.

### Basic Usage

```python
from src.hybrid_reader import HybridReader

# Same .read() interface for all readers
text = HybridReader().read("invoice.pdf")
```

### Batch Processing

```python
from src.utils import batch_read, find_pdfs, find_documents

# Read every PDF in a folder
results = batch_read("path/to/pdfs", output_dir="output")

# Find PDFs or images
pdfs = find_pdfs("path/to/pdfs")
images = find_documents("path/to/pdfs", {".png", ".jpg"})
```

### Benchmark

```powershell
# Single file — all available readers
python -m src.benchmark invoice.pdf

# Directory scan
python -m src.benchmark --batch tests/fixtures

# Specific methods only
python -m src.benchmark invoice.pdf --methods pymupdf docling hybrid

# Custom Tesseract path
python -m src.benchmark --batch . --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Single-file mode shows a summary table with time, characters, unique words, word overlap, and speed ratios. Results are exported to `results/<filename>_benchmark.json`.

---

## Recommended Strategy for IDP

For Invoice Data Processing (IDP) with thousands of daily PDFs:

**Use `HybridReader`** — it tries pymupdf first (instant for text-layer PDFs), then falls back to docling OCR only when output is below 100 characters. This gives:

- **Text-layer PDFs** (~75% of invoices): <0.5 seconds
- **Scanned PDFs** (~25% of invoices): 20-55 seconds with full OCR quality

Benchmarked against 12 real-world invoices — hybrid produces identical output to docling while running 10-25% faster.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `FileNotFoundError: tesseract is not installed` | Pass path: `PDFReader(tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe")` |
| `PdfInfoNotInstalledError` | Install Poppler (`winget install Poppler`) |
| `ImportError` for a package | Re-run `pip install -r requirements.txt` |
| Docling first run is very slow | Normal — downloads ~300 MB model, cached after |
| Surya/Marker crash on startup | They need a separate venv with `transformers>=5.x` |
| `.venv\Scripts\activate` fails | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |

---

## Project Structure

```
├── results/                 # Benchmark JSON output
├── src/
│   ├── __init__.py          # Public API re-exports
│   ├── document_reader.py   # PDFReader (pypdf + pytesseract OCR)
│   ├── pymupdf_reader.py    # PyMuPDFReader (fitz)
│   ├── pdfplumber_reader.py # PdfPlumberReader
│   ├── docling_reader.py    # DoclingReader
│   ├── unstructured_reader.py # UnstructuredReader
│   ├── hybrid_reader.py     # HybridReader (pymupdf → docling fallback)
│   ├── surya_reader.py      # SuryaReader (pure ONNX OCR)
│   ├── marker_reader.py     # MarkerReader (markdown + layout)
│   ├── image_reader.py      # ImageReader (tesseract/surya/marker)
│   ├── benchmark.py         # Auto-discovers and compares all readers
│   └── utils.py             # find_pdfs(), batch_read(), validation
├── tests/
│   ├── test_benchmark.py
│   ├── test_document_reader.py
│   ├── test_hybrid_reader.py
│   ├── test_surya_reader.py
│   ├── test_marker_reader.py
│   ├── test_image_reader.py
│   └── test_utils.py
├── pyproject.toml           # mypy strict config
├── requirements.txt
├── CONVENTIONS.md           # Naming, typing, and style rules
└── README.md
```
