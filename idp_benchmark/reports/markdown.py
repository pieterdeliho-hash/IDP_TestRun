"""Markdown report generator for benchmark results.

Produces structured, human-readable Markdown with tables for speed,
quality, memory, and failure analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from idp_benchmark.benchmark.runner import BenchmarkRun


def _fmt_time(s: float) -> str:
    """Format seconds as human-readable duration."""
    if s < 60:
        return f"{s:.2f}s"
    return f"{s / 60:.1f}m"


def _fmt_memory(bytes_: int) -> str:
    """Format bytes as human-readable memory."""
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / 1024 / 1024:.1f} MB"


def generate_markdown_report(
    run: BenchmarkRun,
    *,
    output_path: str | Path | None = None,
) -> Path:
    """Generate a comprehensive Markdown benchmark report.

    Args:
        run:         A completed :class:`BenchmarkRun`.
        output_path: Destination file (defaults to ``results/report.md``).

    Returns:
        Path to the generated report.
    """
    out = Path(output_path) if output_path else Path("results/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    a = lines.append

    by_reader = run.results_by_reader()
    reader_names = sorted(by_reader)

    # ── Header ──────────────────────────────────────────────────────
    a("# IDP Benchmark Report")
    a("")
    a(f"**Generated:** {run.timestamp or 'N/A'}")
    a(f"**Total runs:** {len(run.results)}")
    a(f"**Readers:** {', '.join(reader_names)}")
    a(f"**Documents:** {len({r.file_path for r in run.results})}")
    a("")

    # ── Hardware ────────────────────────────────────────────────────
    if run.hardware:
        a("## Hardware")
        a("")
        a("| Component | Detail |")
        a("|-----------|--------|")
        for key, val in run.hardware.items():
            a(f"| {key} | {val} |")
        a("")

    # ── Speed Comparison ────────────────────────────────────────────
    a("## Speed Comparison")
    a("")
    a("| Document | Reader | Time | Chars | Chars/sec | Peak Memory |")
    a("|----------|--------|------|-------|-----------|-------------|")

    for r in sorted(run.results, key=lambda x: (x.file_path, x.reader_name)):
        fname = r.file_path.name
        cps = r.char_count / r.elapsed_seconds if r.elapsed_seconds > 0 else 0
        status = "" if r.success else " **FAILED**"
        a(
            f"| {fname} | {r.reader_name} | {_fmt_time(r.elapsed_seconds)} "
            f"| {r.char_count:,} | {cps:,.0f} | {_fmt_memory(r.memory_peak_bytes)}{status} |"
        )
    a("")

    # ── Total Time Per Reader ───────────────────────────────────────
    a("## Total Time (All Documents)")
    a("")
    a("| Reader | Total Time | Avg Time | Runs | Failures |")
    a("|--------|-----------|----------|------|----------|")

    totals: dict[str, float] = {}
    for name in reader_names:
        t = run.total_time(name)
        if t > 0:
            totals[name] = t

    if totals:
        fastest = min(totals, key=lambda k: totals[k])
        ft = totals[fastest]
        for name in sorted(totals, key=lambda k: totals[k]):
            results = by_reader[name]
            fails = len([r for r in results if not r.success])
            avg = totals[name] / len(results)
            ratio = totals[name] / ft if ft > 0 else 0
            a(
                f"| {name} | {_fmt_time(totals[name])} "
                f"| {_fmt_time(avg)} | {len(results)} | {fails} |"
            )
        a("")
        a(f"**Fastest overall:** `{fastest}` ({_fmt_time(ft)})")
    a("")

    # ── Quality Summary ─────────────────────────────────────────────
    a("## Quality Summary (Characters Extracted)")
    a("")
    a("| Document | Reader | Chars | Unique Words | Status |")
    a("|----------|--------|-------|--------------|--------|")

    for r in sorted(run.results, key=lambda x: (x.file_path, x.reader_name)):
        fname = r.file_path.name
        if r.success:
            status = "scanned" if r.char_count < 50 else "ok"
            a(
                f"| {fname} | {r.reader_name} "
                f"| {r.char_count:,} | {r.unique_word_count:,} | {status} |"
            )
        else:
            a(f"| {fname} | {r.reader_name} | - | - | ERROR |")
    a("")

    # ── Memory Summary ──────────────────────────────────────────────
    a("## Memory Usage (Peak)")
    a("")
    a("| Reader | Avg Peak | Max Peak |")
    a("|--------|----------|----------|")

    for name in reader_names:
        successful = [r for r in by_reader[name] if r.success and r.memory_peak_bytes > 0]
        if successful:
            mems = [r.memory_peak_bytes for r in successful]
            avg_mem = sum(mems) / len(mems)
            a(
                f"| {name} | {_fmt_memory(int(avg_mem))} | {_fmt_memory(max(mems))} |"
            )
    a("")

    # ── Failures ─────────────────────────────────────────────────────
    if run.failed:
        a("## Failures")
        a("")
        for r in run.failed:
            a(
                f"- **{r.file_path.name}** with `{r.reader_name}`: "
                f"{r.error or 'unknown error'}"
            )
        a("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
