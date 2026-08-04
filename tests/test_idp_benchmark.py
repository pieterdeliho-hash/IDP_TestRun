"""Tests for the idp_benchmark framework."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from idp_benchmark.benchmark.metrics import BenchmarkMetrics, detect_hardware
from idp_benchmark.benchmark.runner import BenchmarkRun, Runner
from idp_benchmark.datasets.registry import (
    Dataset,
    get_dataset,
    list_datasets,
    register_dataset,
)
from idp_benchmark.experiments.tracker import ExperimentTracker
from idp_benchmark.pipelines.base import Pipeline, Step
from idp_benchmark.pipelines.extract import (
    ExtractPipeline,
    ExtractStep,
    ReportStep,
    make_extract_pipeline,
)
from idp_benchmark.readers.base import BenchReader, BenchResult


# ── Helper: a concrete BenchReader for testing ──────────────────────


class _FakeReader(BenchReader):
    """Minimal BenchReader that returns predictable text."""

    def __init__(self, name: str = "fake", text: str = "hello world") -> None:
        super().__init__(name)
        self._text = text

    def extract(self, file_path: str | Path) -> str:
        return self._text


class TestBenchResult:
    def test_char_count(self) -> None:
        r = BenchResult(
            reader_name="x", file_path=Path("a.pdf"), text="abc def",
            elapsed_seconds=0.1, memory_peak_bytes=1000, success=True,
        )
        assert r.char_count == 7

    def test_unique_word_count(self) -> None:
        r = BenchResult(
            reader_name="x", file_path=Path("a.pdf"), text="a b a c",
            elapsed_seconds=0.1, memory_peak_bytes=1000, success=True,
        )
        assert r.unique_word_count == 3

    def test_empty_text(self) -> None:
        r = BenchResult(
            reader_name="x", file_path=Path("a.pdf"), text="",
            elapsed_seconds=0.1, memory_peak_bytes=1000, success=True,
        )
        assert r.unique_word_count == 0


class TestBenchReader:
    def test_run_success(self) -> None:
        reader = _FakeReader("fake", "test text")
        result = reader.run("any.pdf")
        assert result.success
        assert result.text == "test text"
        assert result.elapsed_seconds >= 0
        assert result.memory_peak_bytes >= 0

    def test_run_failure(self) -> None:
        class _BadReader(BenchReader):
            def extract(self, file_path: str | Path) -> str:
                raise ValueError("boom")

        reader = _BadReader("bad")
        result = reader.run("any.pdf")
        assert not result.success
        assert result.error == "boom"
        assert result.text == ""

    def test_save_results(self) -> None:
        reader = _FakeReader("fake", "hello")
        d = reader.save_results("f.pdf", "hello", elapsed=0.3)
        assert d["reader"] == "fake"
        assert d["chars"] == 5
        assert d["elapsed_s"] == 0.3


class TestRunner:
    def test_run_single(self) -> None:
        readers = [_FakeReader("r1"), _FakeReader("r2")]
        runner = Runner(readers)
        run = runner.run_single("test.pdf")
        assert len(run.results) == 2
        assert all(r.success for r in run.results)

    def test_run_batch(self) -> None:
        readers = [_FakeReader("r1")]
        runner = Runner(readers)
        run = runner.run_batch(["a.pdf", "b.pdf"])
        assert len(run.results) == 2

    def test_results_by_reader(self) -> None:
        run = BenchmarkRun(results=[
            BenchResult("a", Path("1.pdf"), "x", 0.1, 100, True),
            BenchResult("a", Path("2.pdf"), "y", 0.2, 100, True),
            BenchResult("b", Path("1.pdf"), "z", 0.15, 100, True),
        ])
        by = run.results_by_reader()
        assert len(by["a"]) == 2
        assert len(by["b"]) == 1

    def test_total_time(self) -> None:
        run = BenchmarkRun(results=[
            BenchResult("a", Path("1.pdf"), "x", 0.1, 100, True),
            BenchResult("a", Path("2.pdf"), "y", 0.3, 100, True),
            BenchResult("b", Path("1.pdf"), "z", 0.5, 100, True),
        ])
        assert run.total_time("a") == 0.4
        assert run.total_time("b") == 0.5


class TestBenchmarkMetrics:
    def test_detect_hardware(self) -> None:
        hw = detect_hardware()
        assert "os" in hw
        assert "cpu" in hw
        assert "gpu" in hw
        assert "python_version" in hw

    def test_summary(self) -> None:
        m = BenchmarkMetrics()
        m._entries.append({
            "reader": "r1", "file": "a.pdf",
            "elapsed_s": 0.5, "peak_memory_bytes": 1024, "success": True,
        })
        summary = m.summary()
        assert "r1" in summary
        assert summary["r1"]["total_runs"] == 1

    def test_save_json(self, tmp_path: Path) -> None:
        m = BenchmarkMetrics()
        out = tmp_path / "metrics.json"
        m.save_json(out)
        data = json.loads(out.read_text())
        assert "hardware" in data
        assert "summary" in data


class TestDatasetRegistry:
    def test_register_and_list(self, tmp_path: Path) -> None:
        ds = register_dataset("test_ds", tmp_path, description="test")
        datasets = list_datasets()
        assert "test_ds" in datasets
        assert datasets["test_ds"].description == "test"

    def test_get_dataset(self, tmp_path: Path) -> None:
        register_dataset("get_ds", tmp_path)
        ds = get_dataset("get_ds")
        assert ds is not None
        assert ds.name == "get_ds"

    def test_missing_dataset(self) -> None:
        assert get_dataset("nonexistent") is None


class TestPipeline:
    def test_basic_execution(self) -> None:
        class SetStep(Step):
            def execute(self, context: dict[str, Any]) -> dict[str, Any]:
                context["x"] = 42
                return context

        p = Pipeline("test")
        p.add(SetStep(name="set"))
        ctx = p.run()
        assert ctx["x"] == 42

    def test_chaining(self) -> None:
        class IncStep(Step):
            def execute(self, context: dict[str, Any]) -> dict[str, Any]:
                context["n"] = context.get("n", 0) + 1
                return context

        p = Pipeline("chain")
        p.add(IncStep(name="a")).add(IncStep(name="b"))
        ctx = p.run()
        assert ctx["n"] == 2


class TestExtractPipeline:
    def test_factory(self) -> None:
        readers = [_FakeReader("fake")]
        p = make_extract_pipeline(readers)
        assert len(p.steps) == 2
        assert isinstance(p.steps[0], ExtractStep)
        assert isinstance(p.steps[1], ReportStep)

    def test_alias_is_pipeline(self) -> None:
        assert ExtractPipeline is Pipeline


class TestExperimentTracker:
    def test_save_creates_directory(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(tmp_path / "exps")
        run = BenchmarkRun(
            results=[
                BenchResult("r1", Path("a.pdf"), "hello", 0.1, 500, True),
            ],
            hardware={"cpu": "test"},
            timestamp="2024-01-01T00:00:00",
        )
        exp_dir = tracker.save(run, name="test_run")
        assert exp_dir.is_dir()
        assert (exp_dir / "metadata.json").exists()
        assert (exp_dir / "results.json").exists()
        assert (exp_dir / "report.md").exists()
        assert (exp_dir / "config.json").exists()

    def test_metadata_content(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(tmp_path / "exps")
        run = BenchmarkRun(
            results=[
                BenchResult("r1", Path("a.pdf"), "hello", 0.1, 500, True),
            ],
            hardware={"cpu": "test"},
            timestamp="2024-01-01T00:00:00",
        )
        exp_dir = tracker.save(run, name="meta_test")
        meta = json.loads((exp_dir / "metadata.json").read_text())
        assert meta["experiment_id"].startswith("meta_test_")
        assert meta["reader_names"] == ["r1"]
        assert meta["document_count"] == 1
