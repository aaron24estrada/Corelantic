"""Errors raised when a query intent does not fit the semantic model.

Every one of these is the *caller's* mistake: a metric we do not define, a dimension the
metric cannot be sliced by, a time question with no date to anchor it. They map to 422 at
the HTTP boundary and each carries ``allowed`` — the vocabulary that *would* have been
accepted — so the caller repairs the intent instead of retrying blind. The agent re-plans
from it, and the dashboard's error state names the options rather than saying "failed".

Contrast app/semantic/errors.py: those are definition-time faults in the registry itself.
They are our mistakes, not the caller's, and must never surface to a client as a 4xx.
"""

from enum import StrEnum
from typing import ClassVar


class IntentErrorCode(StrEnum):
    UNKNOWN_METRIC = "unknown_metric"
    UNKNOWN_DIMENSION = "unknown_dimension"
    INCOMPATIBLE_DIMENSION = "incompatible_dimension"
    DATE_DIMENSION = "date_dimension"


class IntentError(Exception):
    """Base for intent-validation failures. ``code`` is stable; the message is not."""

    code: ClassVar[IntentErrorCode]

    def __init__(self, message: str, *, field: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.field = field
        self.allowed = allowed


class MetricNotDefinedError(IntentError):
    code: ClassVar[IntentErrorCode] = IntentErrorCode.UNKNOWN_METRIC

    def __init__(self, name: str, allowed: list[str]) -> None:
        super().__init__(f"Unknown metric {name!r}.", field="metric", allowed=allowed)
        self.name = name


class DimensionNotDefinedError(IntentError):
    code: ClassVar[IntentErrorCode] = IntentErrorCode.UNKNOWN_DIMENSION

    def __init__(self, name: str, field: str, allowed: list[str]) -> None:
        super().__init__(f"Unknown dimension {name!r}.", field=field, allowed=allowed)
        self.name = name


class IncompatibleDimensionError(IntentError):
    """The dimension is defined, but this metric cannot be sliced by it.

    Three causes, one remedy — pick a dimension from ``allowed`` — so they share a code and
    explain themselves in the message:

    *No join path*: the entities are simply unrelated in the model.
    *Fan-out*: the join is one-to-many and would multiply the fact rows, inflating every
    measure built on them.
    *Filtered measure*: the metric's own measure already pins that column, so "voucher rate
    by stage" would read 100% for the voucher stage and 0% everywhere else. The question is
    malformed, not the data — refuse it rather than answer it misleadingly.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.INCOMPATIBLE_DIMENSION

    def __init__(
        self, metric: str, dimension: str, reason: str, field: str, allowed: list[str]
    ) -> None:
        super().__init__(
            f"Metric {metric!r} cannot be sliced by dimension {dimension!r}: {reason}.",
            field=field,
            allowed=allowed,
        )
        self.metric = metric
        self.dimension = dimension
        self.reason = reason


class DateDimensionError(IntentError):
    """A time question could not be anchored to exactly one date dimension.

    Grain bucketing, date ranges, and the temporal metric types all need one date to bucket
    and range on. Raised when none is reachable, when several are and the intent named none
    (which date a question means changes the answer, so we never guess), or when the named
    one is not a date or is not safely joinable.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.DATE_DIMENSION

    def __init__(self, reason: str, allowed: list[str]) -> None:
        super().__init__(reason, field="date_dimension", allowed=allowed)
