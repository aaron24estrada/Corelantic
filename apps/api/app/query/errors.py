"""Errors raised while compiling a query intent into SQL."""


class CompileError(Exception):
    """Base for query-compilation failures."""


class FilteredMeasureConflictError(CompileError):
    """A metric is sliced by the very column one of its measures already filters on.

    The measure's predicate pins that column, so every other group has an empty aggregate:
    "voucher rate by stage" reads as 100% for the voucher stage and 0% everywhere else. The
    question is malformed, not the data — refuse it rather than answer it misleadingly.
    """

    def __init__(self, metric: str, dimension: str) -> None:
        super().__init__(
            f"Metric {metric!r} filters on the column behind dimension {dimension!r}; "
            "grouping or filtering by it would be meaningless."
        )
        self.metric = metric
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
