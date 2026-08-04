"""Benchmark runner — orchestrates readers over datasets.

The ``Runner`` class is the main entry point for a benchmark session.
It takes a collection of ``BenchReader`` instances, iterates over
documents, collects :class:`BenchResult` objects, and delegates
reporting to the ``reports`` module.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from idp_benchmark.benchmark.metrics import BenchmarkMetrics
from idp_benchmark.readers.base import BenchReader, BenchResult

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRun:
    """Container for a completed benchmark run.

    Holds per-document results, metadata, and summary statistics.
    """

    results: list[BenchResult] = field(default_factory=list)
    hardware: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    @property
    def successful(self) -> list[BenchResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[BenchResult]:
        return [r for r in self.results if not r.success]

    def results_by_reader(self) -> dict[str, list[BenchResult]]:
        by_reader: dict[str, list[BenchResult]] = {}
        for r in self.results:
            by_reader.setdefault(r.reader_name, []).append(r)
        return by_reader

    def total_time(self, reader_name: str) -> float:
        return sum(
            r.elapsed_seconds
            for r in self.results
            if r.reader_name == reader_name and r.success
        )


class Runner:
    """Execute benchmarks across readers and documents.

    Args:
        readers: List of :class:`BenchReader` instances to evaluate.

    Example::

        runner = Runner(readers=[pymupdf_reader, docling_reader])
        run = runner.run_files(["invoice1.pdf", "invoice2.pdf"])
        generate_markdown_report(run, output_path="report.md")
    """

    def __init__(self, readers: Sequence[BenchReader]) -> None:
        self.readers = readers
        self.metrics = BenchmarkMetrics()

    def run_single(
        self,
        file_path: str | Path,
        readers: Sequence[BenchReader] | None = None,
    ) -> BenchmarkRun:
        """Run selected readers on a single document.

        Args:
            file_path: Path to the document.
            readers:   Subset of readers to run (defaults to all).

        Returns:
            A :class:`BenchmarkRun` with results for each reader.
        """
        targets = readers or self.readers
        results: list[BenchResult] = []

        for reader in targets:
            logger.info("Running %s on %s", reader.name, file_path)
            result = reader.run(file_path)
            results.append(result)
            if result.success:
                logger.info(
                    "  %s: %.2fs, %d chars, %.1f MB peak",
                    reader.name,
                    result.elapsed_seconds,
                    result.char_count,
                    result.memory_peak_bytes / 1024 / 1024,
                )
            else:
                logger.warning("  %s FAILED: %s", reader.name, result.error)

        import time

        return BenchmarkRun(
            results=results,
            hardware=self.metrics.hardware,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def run_batch(
        self,
        file_paths: Sequence[str | Path],
        readers: Sequence[BenchReader] | None = None,
    ) -> BenchmarkRun:
        """Run selected readers on multiple documents.

        Iteration order: file-outer, reader-inner (all readers on file 1,
        then all readers on file 2, …) for easy progress tracking.

        Args:
            file_paths: List of document paths.
            readers:    Subset of readers to run (defaults to all).

        Returns:
            A :class:`BenchmarkRun` with all results.
        """
        targets = readers or self.readers
        results: list[BenchResult] = []

        for fpath in file_paths:
            for reader in targets:
                logger.info("Running %s on %s", reader.name, fpath)
                result = reader.run(fpath)
                results.append(result)
                if result.success:
                    logger.info(
                        "  %s (%s): %.2fs, %d chars",
                        reader.name,
                        Path(fpath).name,
                        result.elapsed_seconds,
                        result.char_count,
                    )
                else:
                    logger.warning(
                        "  %s (%s) FAILED: %s",
                        reader.name,
                        Path(fpath).name,
                        result.error,
                    )

        import time

        return BenchmarkRun(
            results=results,
            hardware=self.metrics.hardware,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
