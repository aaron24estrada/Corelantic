"""Errors raised while compiling a query intent into SQL."""

from app.semantic.models import Dimension, Metric


class CompileError(Exception):
    """Base for query-compilation failures."""


class CrossSourceError(CompileError):
    """A dimension is not on the metric's source.

    The MVP compiler is single-source: every grouped or filtered dimension must live on
    the same table or view as the metric. Cross-source joins are a later capability.
    """

    def __init__(self, metric: Metric, dimension: Dimension) -> None:
        super().__init__(
            f"Dimension {dimension.name!r} (source {dimension.source!r}) is not on "
            f"metric {metric.name!r}'s source ({metric.source!r})."
        )
        self.metric = metric
        self.dimension = dimension
