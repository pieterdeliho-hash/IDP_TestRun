"""Report generators."""

from __future__ import annotations

from idp_benchmark.reports.markdown import generate_markdown_report
from idp_benchmark.reports.json_report import generate_json_report

__all__ = [
    "generate_json_report",
    "generate_markdown_report",
]
