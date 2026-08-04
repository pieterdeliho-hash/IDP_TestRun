"""Extract pipeline — runs all registered readers over a document set.

The ``ExtractPipeline`` assembles an ``ExtractStep`` that uses the
:class:`Runner` to process files, then an optional ``ReportStep``
to generate markdown and JSON outputs.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from idp_benchmark.benchmark.runner import BenchmarkRun, Runner
from idp_benchmark.pipelines.base import Pipeline, Step
from idp_benchmark.readers.base import BenchReader

logger = logging.getLogger(__name__)


class ExtractStep(Step):
    """Pipeline step: run readers on documents."""

    def __init__(
        self,
        readers: Sequence[BenchReader],
        *,
        step_name: str = "extract",
    ) -> None:
        super().__init__(name=step_name)
        self._runner = Runner(readers)

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        file_paths = context.get("file_paths", [])
        readers = context.get("readers")

        if not file_paths:
            logger.warning("ExtractStep: no file_paths in context, skipping")
            return context

        benchmark_readers: Sequence[BenchReader] = readers or self._runner.readers
        run = self._runner.run_batch(file_paths, readers=benchmark_readers)
        context["benchmark_run"] = run
        return context


class ReportStep(Step):
    """Pipeline step: generate benchmark reports."""

    def __init__(
        self,
        output_dir: str | Path = "results",
        *,
        step_name: str = "report",
    ) -> None:
        super().__init__(name=step_name)
        self._output_dir = Path(output_dir)

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        run: BenchmarkRun | None = context.get("benchmark_run")
        if run is None:
            logger.warning("ReportStep: no benchmark_run in context, skipping")
            return context

        self._output_dir.mkdir(parents=True, exist_ok=True)

        from idp_benchmark.reports.markdown import generate_markdown_report
        from idp_benchmark.reports.json_report import generate_json_report

        md_path = self._output_dir / "report.md"
        generate_markdown_report(run, output_path=md_path)
        logger.info("Markdown report: %s", md_path)

        json_path = self._output_dir / "report.json"
        generate_json_report(run, output_path=json_path)
        logger.info("JSON report: %s", json_path)

        context["report_paths"] = {
            "markdown": str(md_path),
            "json": str(json_path),
        }
        return context


def make_extract_pipeline(
    readers: Sequence[BenchReader],
    *,
    output_dir: str | Path = "results",
) -> Pipeline:
    """Convenience factory for a standard extract-and-report pipeline.

    Args:
        readers:    BenchReader instances to evaluate.
        output_dir: Where to write reports.

    Returns:
        A configured :class:`Pipeline`.
    """
    pipeline = Pipeline("extract_and_report")
    pipeline.add(ExtractStep(readers))
    pipeline.add(ReportStep(output_dir=output_dir))
    return pipeline


# Aliased for backwards compatibility with __init__.py exports
ExtractPipeline = Pipeline
