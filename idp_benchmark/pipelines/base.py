"""Composable pipeline base — ordered step execution for benchmark workflows.

A :class:`Pipeline` chains steps where each step receives the output of
the previous one.  This enables workflows like:

    extract -> evaluate -> report -> save_experiment
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Step(ABC):
    """A single pipeline step.

    Subclasses implement ``execute()`` which receives the context
    dict carrying forward data from previous steps.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run this step and update the context.

        Args:
            context: Shared dict with inputs from prior steps.

        Returns:
            An updated context dict (may be the same object).
        """


class Pipeline:
    """Run a sequence of steps in order.

    Args:
        name: Pipeline identifier.

    Example::

        pipeline = Pipeline("full_benchmark")
        pipeline.add(ExtractStep(readers))
        pipeline.add(EvaluateStep())
        pipeline.add(ReportStep(output_dir="reports/"))
        context = pipeline.run(input_files=files)
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._steps: list[Step] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def steps(self) -> list[Step]:
        return list(self._steps)

    def add(self, step: Step) -> Pipeline:
        """Append a step.  Returns self for chaining."""
        self._steps.append(step)
        return self

    def run(self, **initial_context: Any) -> dict[str, Any]:
        """Execute all steps in order.

        Args:
            initial_context: Key-value pairs passed to the first step.

        Returns:
            The final context dict after all steps.
        """
        context: dict[str, Any] = dict(initial_context)

        for step in self._steps:
            logger.info("Pipeline [%s]: running step %s", self._name, step.name)
            try:
                context = step.execute(context)
            except Exception:
                logger.exception(
                    "Pipeline [%s]: step %s failed", self._name, step.name
                )
                raise

        logger.info(
            "Pipeline [%s]: all %d steps completed",
            self._name,
            len(self._steps),
        )
        return context
