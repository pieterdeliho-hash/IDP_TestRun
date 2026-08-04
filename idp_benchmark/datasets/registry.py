"""Dataset registry — manages benchmark document collections.

Datasets are named directories (or lists of files) that can be
referenced by name in configs, pipelines, and experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Dataset:
    """A named collection of benchmark documents."""

    name: str
    path: str | Path
    description: str = ""
    document_types: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def files(self) -> list[Path]:
        """Return sorted list of files in the dataset."""
        p = Path(self.path)
        if p.is_file():
            return [p]
        if p.is_dir():
            return sorted(
                f for f in p.rglob("*")
                if f.is_file() and f.suffix.lower()
                in {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
            )
        return []

    @property
    def file_count(self) -> int:
        return len(self.files)


# Global registry
_dataset_registry: dict[str, Dataset] = {}


def register_dataset(
    name: str,
    path: str | Path,
    *,
    description: str = "",
    document_types: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Dataset:
    """Register a benchmark dataset.

    Args:
        name:           Unique dataset identifier.
        path:           Directory or file path.
        description:    Human-readable description.
        document_types: Categories like ``["invoice"]``, ``["contract"]``.
        metadata:       Arbitrary key-value pairs.

    Returns:
        The created :class:`Dataset`.
    """
    ds = Dataset(
        name=name,
        path=path,
        description=description,
        document_types=document_types or [],
        metadata=metadata or {},
    )
    _dataset_registry[name] = ds
    return ds


def list_datasets() -> dict[str, Dataset]:
    """Return all registered datasets."""
    return dict(_dataset_registry)


def get_dataset(name: str) -> Dataset | None:
    """Look up a dataset by name."""
    return _dataset_registry.get(name)
