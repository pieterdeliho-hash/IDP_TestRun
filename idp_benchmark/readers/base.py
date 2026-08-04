"""Base interface for benchmark-aware document readers.

Every library that participates in the benchmark implements the
``BenchReader`` abstract base class.  The interface separates the
extraction logic from timing, persistence, and orchestration so that
the runner can compose any reader without knowing its internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchResult:
    """Structured result of a single reader-on-one-document run."""

    reader_name: str
    file_path: Path
    text: str
    elapsed_seconds: float
    memory_peak_bytes: int
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def unique_word_count(self) -> int:
        if not self.text:
            return 0
        return len(set(self.text.lower().split()))


class BenchReader(ABC):
    """Abstract base class for benchmark-integrated document readers.

    Subclasses implement ``extract()`` for the actual text extraction.
    The remaining methods provide timing, memory tracking, and result
    persistence out of the box.
    """

    def __init__(self, name: str, *, config: dict[str, Any] | None = None) -> None:
        """Initialize a benchmark reader.

        Args:
            name:   Human-readable identifier (e.g. ``"pymupdf"``).
            config: Optional library-specific configuration dictionary.
        """
        self._name = name
        self._config: dict[str, Any] = config or {}

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def extract(self, file_path: str | Path) -> str:
        """Extract text from a document.

        Args:
            file_path: Path to the document.

        Returns:
            The full extracted text.
        """

    def measure_time(self, file_path: str | Path) -> float:
        """Run ``extract()`` and return the wall-clock elapsed time.

        Args:
            file_path: Path to the document.

        Returns:
            Elapsed time in seconds.
        """
        import time

        start = time.perf_counter()
        self.extract(file_path)
        return time.perf_counter() - start

    def save_results(
        self,
        file_path: str | Path,
        text: str,
        *,
        elapsed: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Package extraction results into a serializable dict.

        Args:
            file_path: Path to the document.
            text:      Extracted text.
            elapsed:   Wall-clock extraction time in seconds.
            metadata:  Additional key-value pairs to attach.

        Returns:
            A dict suitable for JSON serialization.
        """
        return {
            "reader": self.name,
            "file": str(file_path),
            "text": text,
            "chars": len(text),
            "unique_words": len(set(text.lower().split())) if text else 0,
            "elapsed_s": round(elapsed, 4),
            "metadata": metadata or {},
        }

    def run(self, file_path: str | Path) -> BenchResult:
        """Full extraction with timing and memory tracking.

        The default implementation measures peak Python memory via
        ``tracemalloc``.  Override to use a different profiler.

        Args:
            file_path: Path to the document.

        Returns:
            A :class:`BenchResult` with timing, memory, and text.
        """
        import tracemalloc
        import time

        tracemalloc.start()
        start = time.perf_counter()

        try:
            text = self.extract(file_path)
            elapsed = time.perf_counter() - start
            _, peak = tracemalloc.get_traced_memory()
            return BenchResult(
                reader_name=self.name,
                file_path=Path(file_path),
                text=text,
                elapsed_seconds=elapsed,
                memory_peak_bytes=peak,
                success=True,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return BenchResult(
                reader_name=self.name,
                file_path=Path(file_path),
                text="",
                elapsed_seconds=elapsed,
                memory_peak_bytes=0,
                success=False,
                error=str(exc),
            )
        finally:
            tracemalloc.stop()
