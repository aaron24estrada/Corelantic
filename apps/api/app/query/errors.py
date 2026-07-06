"""Errors raised while compiling a query intent into SQL."""


class CompileError(Exception):
    """Base for query-compilation failures."""


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
