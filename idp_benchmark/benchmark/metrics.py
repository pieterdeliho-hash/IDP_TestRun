"""Benchmark metrics collection and hardware detection.

Centralizes timing, memory, and system-info utilities so every
runner and report uses the same numbers.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkMetrics:
    """Accumulates metrics across a benchmark run.

    Usage::

        metrics = BenchmarkMetrics()
        for reader, doc in combos:
            result = metrics.timed_run(reader.extract, doc)
        report = metrics.summary()
    """

    _entries: list[dict[str, Any]] = field(default_factory=list)
    hardware: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.hardware:
            self.hardware = detect_hardware()

    def timed_run(
        self,
        func: object,
        *args: object,
        reader_name: str = "",
        file_path: str | Path = "",
        **kwargs: object,
    ) -> tuple[object, float, int]:
        """Execute *func* with timing and peak-memory tracking.

        Args:
            func:      Callable to benchmark.
            reader_name: Identifier for the reader.
            file_path: Document being processed.

        Returns:
            ``(return_value, elapsed_seconds, peak_memory_bytes)``
        """
        tracemalloc.start()
        start = time.perf_counter()
        try:
            # func is typed as object to avoid importing every reader type
            result = func(*args, **kwargs)  # type: ignore[operator]
            elapsed = time.perf_counter() - start
            _, peak = tracemalloc.get_traced_memory()
            self._entries.append({
                "reader": reader_name,
                "file": str(file_path),
                "elapsed_s": round(elapsed, 4),
                "peak_memory_bytes": peak,
                "success": True,
            })
            return result, elapsed, peak
        except Exception as exc:
            elapsed = time.perf_counter() - start
            self._entries.append({
                "reader": reader_name,
                "file": str(file_path),
                "elapsed_s": round(elapsed, 4),
                "peak_memory_bytes": 0,
                "success": False,
                "error": str(exc),
            })
            raise
        finally:
            tracemalloc.stop()

    def summary(self) -> dict[str, Any]:
        """Compute aggregate statistics.

        Returns:
            Dict with per-reader totals, averages, and counts.
        """
        by_reader: dict[str, list[dict[str, Any]]] = {}
        for entry in self._entries:
            by_reader.setdefault(entry["reader"], []).append(entry)

        summary: dict[str, dict[str, Any]] = {}
        for reader, entries in by_reader.items():
            successes = [e for e in entries if e["success"]]
            failures = [e for e in entries if not e["success"]]
            times = [e["elapsed_s"] for e in successes]
            memories = [e["peak_memory_bytes"] for e in successes]
            summary[reader] = {
                "total_runs": len(entries),
                "successes": len(successes),
                "failures": len(failures),
                "total_time_s": round(sum(times), 3) if times else 0,
                "avg_time_s": round(sum(times) / len(times), 3) if times else 0,
                "min_time_s": round(min(times), 3) if times else 0,
                "max_time_s": round(max(times), 3) if times else 0,
                "avg_peak_memory_mb": round(
                    sum(memories) / len(memories) / 1024 / 1024, 2
                )
                if memories
                else 0,
            }
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Serialize all data for JSON export."""
        return {
            "hardware": self.hardware,
            "entries": self._entries,
            "summary": self.summary(),
        }

    def save_json(self, path: str | Path) -> None:
        """Write full metrics to a JSON file."""
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2), encoding="utf-8"
        )


def detect_hardware() -> dict[str, str]:
    """Detect CPU and GPU hardware for benchmark context.

    Returns:
        Dict with os, cpu, gpu, and python_version keys.
    """
    info: dict[str, str] = {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or "unknown",
        "gpu": "none",
        "python_version": platform.python_version(),
    }

    # Try nvidia-smi for GPU detection
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["gpu"] = result.stdout.strip().split("\n")[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: try torch CUDA detection
    if info["gpu"] == "none":
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                info["gpu"] = torch.cuda.get_device_name(0)
        except ImportError:
            pass

    return info
