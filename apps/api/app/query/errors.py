"""Errors raised while compiling a query intent into SQL."""

from app.semantic.models import Dimension, Measure


class CompileError(Exception):
    """Base for query-compilation failures."""


class CrossEntityError(CompileError):
    """A dimension is not on the measure's entity.

    The MVP compiler is single-entity: every grouped or filtered dimension must live on
    the same entity (table or view) as the metric's measure. Cross-entity joins are a
    later capability.
    """

    def __init__(self, measure: Measure, dimension: Dimension) -> None:
        super().__init__(
            f"Dimension {dimension.name!r} (entity {dimension.entity!r}) is not on "
            f"measure {measure.name!r}'s entity ({measure.entity!r})."
        )
        self.measure = measure
        self.dimension = dimension
