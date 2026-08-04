"""JSON report generator for benchmark results.

Produces a structured JSON file with per-reader metrics, hardware
info, and timestamp for downstream analysis or re-import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from idp_benchmark.benchmark.runner import BenchmarkRun


def generate_json_report(
    run: BenchmarkRun,
    *,
    output_path: str | Path | None = None,
) -> Path:
    """Generate a JSON benchmark report.

    Args:
        run:         A completed :class:`BenchmarkRun`.
        output_path: Destination file (defaults to ``results/report.json``).

    Returns:
        Path to the generated report.
    """
    out = Path(output_path) if output_path else Path("results/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    by_reader = run.results_by_reader()
    reader_names = sorted(by_reader)

    data: dict[str, Any] = {
        "timestamp": run.timestamp,
        "hardware": run.hardware,
        "config": run.config,
        "summary": {},
        "results": [],
    }

    # Per-reader summary
    for name in reader_names:
        results = by_reader[name]
        successful = [r for r in results if r.success]
        times = [r.elapsed_seconds for r in successful]
        chars = [r.char_count for r in successful]
        memories = [r.memory_peak_bytes for r in successful]

        data["summary"][name] = {
            "total_runs": len(results),
            "successes": len(successful),
            "failures": len(results) - len(successful),
            "total_time_s": round(sum(times), 3) if times else 0,
            "avg_time_s": round(sum(times) / len(times), 3) if times else 0,
            "total_chars": sum(chars),
            "avg_chars": round(sum(chars) / len(chars)) if chars else 0,
            "avg_peak_memory_mb": round(
                sum(memories) / len(memories) / 1024 / 1024, 2
            )
            if memories
            else 0,
        }

    # Per-result entries (text excluded to keep file manageable)
    for r in run.results:
        data["results"].append({
            "reader": r.reader_name,
            "file": r.file_path.name,
            "success": r.success,
            "elapsed_s": round(r.elapsed_seconds, 4),
            "chars": r.char_count,
            "unique_words": r.unique_word_count,
            "peak_memory_mb": round(r.memory_peak_bytes / 1024 / 1024, 2),
            "error": r.error,
        })

    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out
