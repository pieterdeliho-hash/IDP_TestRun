"""Benchmark: compare all document readers on speed and output quality."""

from __future__ import annotations

import difflib
import importlib
import json
import time
from pathlib import Path
from typing import Any

from src.utils import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    ReaderProtocol,
    find_documents,
    find_pdfs,
)

# ── Registry of available readers ────────────────────────────────────

READERS: dict[str, dict[str, Any]] = {
    # PDF readers
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
    # Surya and Marker require transformers>=5.x + Pillow<11, which conflicts
    # with docling (transformers<5) and pdfplumber (Pillow>=12.2).
    # They need a separate virtual environment. Disabled here.
    # "surya": { ... },
    # "marker": { ... },
    # Image readers
    "image+tesseract": {
        "module": "src.image_reader",
        "class": "ImageReader",
        "formats": ["image"],
        "args": {"backend": "tesseract"},
    },
}

# Package discovery map
_PKG_MAP: dict[str, list[str]] = {
    "pypdf+ocr": ["pypdf"],
    "pymupdf": ["fitz"],
    "pdfplumber": ["pdfplumber"],
    "docling": ["docling"],
    "unstructured": ["unstructured"],
    "hybrid": ["fitz", "docling"],
    "image+tesseract": ["pytesseract"],
}


def _detect_format(file_path: Path) -> str:
    """Detect document format from extension."""
    ext = file_path.suffix.lower()
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def discover_readers(
    *, file_format: str | None = None
) -> dict[str, dict[str, Any]]:
    """Return only the readers whose packages are installed.

    Args:
        file_format: If set, only return readers for this format.
    """
    available: dict[str, dict[str, Any]] = {}
    for name, cfg in READERS.items():
        if file_format and file_format not in cfg.get("formats", []):
            continue
        try:
            for pkg in _PKG_MAP[name]:
                importlib.import_module(pkg)
            available[name] = cfg
        except ImportError as e:
            print(
                f"  Skipping {name}: {e.name} not installed ({e})",
                file=__import__("sys").stderr,
            )
    return available


def create_reader(
    name: str, tesseract_cmd: str | None = None
) -> ReaderProtocol:
    """Instantiate a reader by registry name."""
    cfg = READERS[name]
    mod = importlib.import_module(cfg["module"])
    cls = getattr(mod, cfg["class"])
    args = cfg.get("args", {})
    if name == "pypdf+ocr":
        return cls(tesseract_cmd=tesseract_cmd, **args)  # type: ignore[no-any-return]
    return cls(**args)  # type: ignore[no-any-return]


# ── Timing ───────────────────────────────────────────────────────────


def read_timed(
    reader: ReaderProtocol, file_path: str | Path
) -> tuple[str, float]:
    """Read a document with a reader instance and measure elapsed time.

    Returns:
        (extracted_text, elapsed_seconds)
    """
    start = time.perf_counter()
    text = reader.read(file_path)
    elapsed = time.perf_counter() - start
    return text, elapsed


# ── Comparison helpers ───────────────────────────────────────────────


def unified_diff(a: str, b: str, label_a: str, label_b: str) -> str:
    """Return a unified diff string between two texts."""
    lines_a = a.splitlines(keepends=True)
    lines_b = b.splitlines(keepends=True)
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b)
    return "".join(diff)


def word_stats(
    texts: dict[str, str],
    *,
    baseline: str | None = None,
) -> dict[str, dict[str, int]]:
    """Compute word-set overlap between the baseline method and every other.

    Args:
        texts:     Method-name -> extracted text mapping.
        baseline:  Which method to use as the reference. Defaults to the
                   method that produced the largest unique word count.

    Returns:
        Dict of method-name -> overlap statistics.
    """
    names = list(texts)
    if len(names) < 2:
        return {}

    if baseline is None:
        baseline = max(names, key=lambda n: len(set(texts[n].lower().split())))

    base = set(texts[baseline].lower().split())
    stats: dict[str, dict[str, int]] = {}
    for name in names:
        if name == baseline:
            continue
        words = set(texts[name].lower().split())
        stats[name] = {
            "common": len(base & words),
            "only_base": len(base - words),
            "only_this": len(words - base),
            "total_base": len(base),
            "total_this": len(words),
        }
    return stats


# ── Result export ────────────────────────────────────────────────────


def _results_dir() -> Path:
    """Return the results directory, creating it if needed."""
    d = Path("results")
    d.mkdir(exist_ok=True)
    return d


def export_json(
    pdf_path: Path,
    results: dict[str, tuple[str, float]],
    stats: dict[str, dict[str, int]],
    base_name: str,
) -> Path:
    """Export benchmark results to a JSON file."""
    out = _results_dir() / f"{pdf_path.stem}_benchmark.json"

    data: dict[str, Any] = {
        "file": pdf_path.name,
        "size_kb": round(pdf_path.stat().st_size / 1024, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "baseline": base_name,
        "readers": {},
    }

    for name, (text, elapsed) in results.items():
        words = len(set(text.lower().split()))
        s = stats.get(name, {})
        data["readers"][name] = {
            "time_s": round(elapsed, 3),
            "chars": len(text),
            "unique_words": words,
            "overlap_common": s.get("common", 0),
            "overlap_only_baseline": s.get("only_base", 0),
            "overlap_only_this": s.get("only_this", 0),
        }

    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


# ── Single-file benchmark ───────────────────────────────────────────


def run_single(
    file_path: str | Path,
    tesseract_cmd: str | None = None,
    methods: list[str] | None = None,
) -> None:
    """Run a side-by-side comparison on a single document."""
    file_path = Path(file_path)
    fmt = _detect_format(file_path)

    if fmt == "unknown":
        print(f"Unsupported file format: {file_path.suffix}")
        return

    avail = discover_readers(file_format=fmt)
    if methods:
        avail = {k: v for k, v in avail.items() if k in methods}

    if not avail:
        print("No readers available. Install at least one package.")
        return

    print(f"\n{'='*72}")
    print(f"  File: {file_path.name}")
    print(f"  Format: {fmt.upper()}")
    print(f"  Size: {file_path.stat().st_size / 1024:.1f} KB")
    print(f"  Methods: {', '.join(avail)}")
    print(f"{'='*72}\n")

    results: dict[str, tuple[str, float]] = {}

    for name in avail:
        try:
            reader = create_reader(name, tesseract_cmd=tesseract_cmd)
            print(f"  {name} ...", end=" ", flush=True)
            text, elapsed = read_timed(reader, file_path)
            results[name] = (text, elapsed)
            print(f"{elapsed:.2f}s  ({len(text)} chars)")
        except Exception as e:
            print(f"FAILED: {e}")

    if not results:
        print("\n  All readers failed.")
        return

    # ── Summary table ──────────────────────────────────────────────
    texts = {n: r[0] for n, r in results.items()}
    base_name = max(texts, key=lambda n: len(set(texts[n].lower().split())))
    stats = word_stats(texts)

    sorted_names = sorted(results, key=lambda n: results[n][1])
    fastest_time = results[sorted_names[0]][1]

    print(f"\n  {'Method':<18} {'Time':>8}  {'Chars':>8}  {'Words':>8}  {'Overlap':>8}  {'Speed':>8}")
    print(f"  {'-'*18}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}")

    for name in sorted_names:
        text, t = results[name]
        chars = len(text)
        words = len(set(text.lower().split()))
        ratio = t / fastest_time if fastest_time > 0 else float("inf")

        if name == base_name:
            overlap = f"100% (ref)"
        else:
            s = stats.get(name)
            if s and s["total_base"] > 0:
                pct = s["common"] / s["total_base"] * 100
                overlap = f"{pct:.0f}%"
            else:
                overlap = "N/A"

        marker = " *" if name == sorted_names[0] else ""
        print(
            f"  {name:<18} {t:>7.2f}s  {chars:>7,}  {words:>7,}  "
            f"{overlap:>8}  {ratio:>5.1f}x{marker}"
        )

    print(f"  * = fastest\n")

    # ── Diff preview vs baseline ───────────────────────────────────
    for name in texts:
        if name == base_name:
            continue
        diff = unified_diff(texts[base_name], texts[name], base_name, name)
        diff_lines = diff.splitlines()
        if diff_lines:
            print(
                f"  Diff {base_name} vs {name} "
                f"({min(len(diff_lines), 20)} of {len(diff_lines)} lines):"
            )
            print("  " + "\n  ".join(diff_lines[:20]))
        else:
            print(f"  {base_name} vs {name}: identical.")

    # ── Export JSON ────────────────────────────────────────────────
    json_path = export_json(file_path, results, stats, base_name)
    print(f"\n  Results saved to {json_path}")


# ── Batch benchmark ─────────────────────────────────────────────────


def run_batch(
    directory: str | Path,
    tesseract_cmd: str | None = None,
    methods: list[str] | None = None,
) -> None:
    """Run comparison on every document in a directory."""
    avail = discover_readers()
    if methods:
        avail = {k: v for k, v in avail.items() if k in methods}

    if not avail:
        print("No readers available. Install at least one package.")
        return

    pdfs = find_pdfs(directory)
    images = find_documents(directory, IMAGE_EXTENSIONS)
    docs = sorted(pdfs + images, key=lambda p: p.name)

    if not docs:
        print(f"No documents found in {directory}")
        return

    # Separate readers by format
    pdf_readers = {n: c for n, c in avail.items() if "pdf" in c.get("formats", [])}
    img_readers = {n: c for n, c in avail.items() if "image" in c.get("formats", [])}

    # Create reader instances
    reader_instances: dict[str, dict[str, ReaderProtocol]] = {"pdf": {}, "image": {}}
    for name in pdf_readers:
        reader_instances["pdf"][name] = create_reader(name, tesseract_cmd=tesseract_cmd)
    for name in img_readers:
        reader_instances["image"][name] = create_reader(name, tesseract_cmd=tesseract_cmd)

    pdf_names = list(reader_instances["pdf"])
    img_names = list(reader_instances["image"])
    all_names = pdf_names + img_names

    # Build header
    col_w = 12
    header = f"  {'File':<30} {'Fmt':<6}" + "".join(f"{m:>{col_w}}" for m in all_names)
    sep = f"  {'-'*30} {'-'*6}" + "".join(f"{'-'*col_w}" for _ in all_names)

    print(f"\n{'='*80}")
    print(f"  Benchmark: {len(docs)} files")
    print(f"  PDF methods: {', '.join(pdf_names) if pdf_names else '(none)'}")
    print(f"  Image methods: {', '.join(img_names) if img_names else '(none)'}")
    print(f"{'='*80}")
    print(header)
    print(sep)

    totals: dict[str, float] = {m: 0.0 for m in all_names}
    all_results: list[dict[str, Any]] = []

    for doc in docs:
        fmt = _detect_format(doc)
        row = f"  {doc.name:<30} {fmt:<6}"
        file_results: dict[str, Any] = {"file": doc.name, "format": fmt, "readers": {}}

        active = reader_instances[fmt]
        for m in all_names:
            if m not in active:
                row += f"{'-':>{col_w}}"
                continue
            try:
                text, t = read_timed(active[m], doc)
                totals[m] += t
                row += f"{t:>{col_w}.2f}"
                file_results["readers"][m] = {
                    "time_s": round(t, 3),
                    "chars": len(text),
                    "words": len(set(text.lower().split())),
                }
            except Exception:
                row += f"{'ERR':>{col_w}}"
                file_results["readers"][m] = {"error": True}

        print(row)
        all_results.append(file_results)

    # Summary
    print(sep)
    total_row = f"  {'TOTAL':<30} {'':<6}" + "".join(
        f"{totals[m]:>{col_w}.2f}" for m in all_names
    )
    print(total_row)

    active_totals = {m: t for m, t in totals.items() if t > 0}
    if active_totals:
        fastest = min(active_totals, key=lambda k: active_totals[k])
        ft = active_totals[fastest]
        print(
            f"  Fastest overall: {fastest}  "
            f"(ratios: "
            + ", ".join(
                f"{m}={totals[m]/ft:.1f}x" for m in all_names if totals[m] > 0
            )
            + ")"
        )

    # ── Quality summary across all files ───────────────────────────
    print(f"\n  Quality summary (chars extracted per file):")
    print(f"  {'File':<30} {'Fmt':<6}", end="")
    for m in all_names:
        print(f"{m:>{col_w}}", end="")
    print()
    print(f"  {'-'*30} {'-'*6}", end="")
    for _ in all_names:
        print(f"{'-'*col_w}", end="")
    print()

    for fr in all_results:
        print(f"  {fr['file']:<30} {fr['format']:<6}", end="")
        for m in all_names:
            r = fr["readers"].get(m, {})
            if not r:
                print(f"{'-':>{col_w}}", end="")
            elif "error" in r:
                print(f"{'ERR':>{col_w}}", end="")
            else:
                print(f"{r['chars']:>{col_w},}", end="")
        print()

    # ── Export JSON ────────────────────────────────────────────────
    out = _results_dir() / "batch_results.json"
    batch_data = {
        "directory": str(directory),
        "files": len(docs),
        "methods": all_names,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "totals": {m: round(totals[m], 3) for m in all_names},
        "fastest": min(active_totals, key=lambda k: active_totals[k]) if active_totals else None,
        "results": all_results,
    }
    out.write_text(json.dumps(batch_data, indent=2), encoding="utf-8")
    print(f"\n  Results saved to {out}")
    print()


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry-point.

    Usage:
        python -m src.benchmark <file_path>             # single file (PDF or image)
        python -m src.benchmark --batch <directory>     # all docs in dir
        python -m src.benchmark file.pdf --methods pypdf+ocr pymupdf
        python -m src.benchmark --batch . --tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare document extraction methods"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", default=None, help="Single document to compare")
    group.add_argument(
        "--batch", "-b", default=None, help="Directory of documents to compare"
    )
    parser.add_argument(
        "--tesseract", "-t", default=None, help="Path to tesseract executable"
    )
    parser.add_argument(
        "--methods", "-m", nargs="+", default=None,
        help="Subset of methods to run (available: "
        + ", ".join(READERS) + ")",
    )
    args = parser.parse_args()

    if args.file:
        run_single(args.file, tesseract_cmd=args.tesseract, methods=args.methods)
    elif args.batch:
        run_batch(args.batch, tesseract_cmd=args.tesseract, methods=args.methods)


if __name__ == "__main__":
    main()
