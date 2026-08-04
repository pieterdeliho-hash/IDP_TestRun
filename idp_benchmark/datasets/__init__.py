"""Dataset registry."""

from __future__ import annotations

from idp_benchmark.datasets.registry import (
    Dataset,
    get_dataset,
    list_datasets,
    register_dataset,
)

__all__ = [
    "Dataset",
    "get_dataset",
    "list_datasets",
    "register_dataset",
]
