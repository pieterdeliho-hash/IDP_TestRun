"""Reader adapters for the benchmark framework."""

from __future__ import annotations

from idp_benchmark.readers.base import BenchReader, BenchResult
from idp_benchmark.readers.registry import (
    create_bench_reader,
    discover_readers,
    register_reader,
)

__all__ = [
    "BenchReader",
    "BenchResult",
    "create_bench_reader",
    "discover_readers",
    "register_reader",
]
