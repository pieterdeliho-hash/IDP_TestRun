"""Experiment tracker — reproducibility for benchmark runs.

Saves a dated experiment directory containing the config, hardware,
git commit, and results so any benchmark can be reproduced later.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from idp_benchmark.benchmark.runner import BenchmarkRun


@dataclass
class ExperimentMetadata:
    """Metadata saved alongside each experiment."""

    experiment_id: str
    timestamp: str
    git_commit: str
    hardware: dict[str, str]
    reader_names: list[str]
    document_count: int
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    """Persist benchmark runs as reproducible experiments.

    Args:
        base_dir: Root directory for experiments (default ``experiments/``).
    """

    def __init__(self, base_dir: str | Path = "experiments") -> None:
        self._base = Path(base_dir)

    def save(
        self,
        run: BenchmarkRun,
        *,
        name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Path:
        """Archive a benchmark run as an experiment.

        Creates a timestamped directory under *base_dir* containing:
        - ``metadata.json`` — hardware, git commit, reader names, etc.
        - ``results.json`` — structured results (reuses JSON report).
        - ``report.md`` — human-readable Markdown report.
        - ``config.json`` — the configuration that produced this run.

        Args:
            run:      A completed :class:`BenchmarkRun`.
            name:     Optional experiment label (slugified for the dir name).
            config:   Configuration dictionary to archive.

        Returns:
            Path to the experiment directory.
        """
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d-%H%M%S")
        label = f"{name}_{ts}" if name else ts
        exp_dir = self._base / label
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Git commit
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True, timeout=5,
            ).strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            commit = "unknown"

        # Config hash
        config = config or run.config or {}
        cfg_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]

        metadata = ExperimentMetadata(
            experiment_id=label,
            timestamp=now.isoformat(),
            git_commit=commit,
            hardware=run.hardware,
            reader_names=sorted({r.reader_name for r in run.results}),
            document_count=len({r.file_path for r in run.results}),
            config_hash=cfg_hash,
        )

        (exp_dir / "metadata.json").write_text(
            json.dumps(metadata.to_dict(), indent=2), encoding="utf-8"
        )

        (exp_dir / "config.json").write_text(
            json.dumps(config, indent=2, default=str), encoding="utf-8"
        )

        from idp_benchmark.reports.json_report import generate_json_report
        from idp_benchmark.reports.markdown import generate_markdown_report

        generate_json_report(run, output_path=exp_dir / "results.json")
        generate_markdown_report(run, output_path=exp_dir / "report.md")

        return exp_dir
