"""IDP (Intelligent Document Processing) Benchmark Framework.

A modular benchmarking framework for comparing document extraction
backends on speed, memory, and output quality.

Sub-modules:
    readers       BenchReader ABC + per-library adapters.
    benchmark     Runner, metrics, hardware detection.
    datasets      Dataset registry for benchmark corpora.
    pipelines     Composable multi-step workflows.
    reports       Markdown and JSON report generators.
    experiments   Reproducibility tracking and result archiving.
"""

from __future__ import annotations

from idp_benchmark.benchmark.runner import Runner
from idp_benchmark.benchmark.metrics import BenchmarkMetrics
from idp_benchmark.readers.base import BenchReader, BenchResult
from idp_benchmark.readers.registry import discover_readers, create_bench_reader
from idp_benchmark.pipelines.base import Pipeline
from idp_benchmark.pipelines.extract import ExtractPipeline
from idp_benchmark.reports.markdown import generate_markdown_report
from idp_benchmark.reports.json_report import generate_json_report
from idp_benchmark.datasets.registry import register_dataset, list_datasets
from idp_benchmark.experiments.tracker import ExperimentTracker

__all__ = [
    "BenchReader",
    "BenchResult",
    "BenchmarkMetrics",
    "ExperimentTracker",
    "ExtractPipeline",
    "Pipeline",
    "Runner",
    "create_bench_reader",
    "discover_readers",
    "generate_json_report",
    "generate_markdown_report",
    "list_datasets",
    "register_dataset",
]
