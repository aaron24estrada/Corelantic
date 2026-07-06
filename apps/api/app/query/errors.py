"""Errors raised while compiling a query intent into SQL."""

from app.semantic.models import Dimension


class CompileError(Exception):
    """Base for query-compilation failures."""


class CrossEntityError(CompileError):
    """A grouped or filtered dimension is not on the metric's entity.

    The MVP compiler is single-entity: every dimension in the query must live on the
    same entity (table or view) the metric's measures do. Cross-entity joins are B3.
    """

    def __init__(self, entity: str, dimension: Dimension) -> None:
        super().__init__(
            f"Dimension {dimension.name!r} (entity {dimension.entity!r}) is not on the "
            f"query entity ({entity!r})."
        )
        self.entity = entity
        self.dimension = dimension


class DateDimensionError(CompileError):
    """A time operation could not resolve which date dimension to use.

    Grain bucketing, date ranges, and the temporal metric types (cumulative, comparison)
    all need a single date dimension on the entity. This is raised when none exists, when
    an entity has several and the intent did not name one, or when the named dimension is
    missing, not temporal, or on another entity.
    """

    def __init__(self, entity: str, reason: str) -> None:
        super().__init__(f"No usable date dimension for entity {entity!r}: {reason}.")
        self.entity = entity
        self.reason = reason
