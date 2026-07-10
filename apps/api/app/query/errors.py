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
    GRAIN_REQUIRED = "grain_required"
    NOT_ADDITIVE = "not_additive"
    ACCUMULATION_RESET = "accumulation_reset"
    PARTIAL_ACCUMULATION = "partial_accumulation"
    DATE_GROUP_BY = "date_group_by"
    COMPARE_WITH_ACCUMULATE = "compare_with_accumulate"


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


class GrainRequiredError(IntentError):
    """A time modifier was asked for without saying how long a period is.

    ``compare`` measures each bucket against the previous one and ``accumulate`` resets each
    period; neither means anything until ``grain`` says what a bucket is.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.GRAIN_REQUIRED

    def __init__(self, modifier: str, allowed: list[str]) -> None:
        super().__init__(
            f"{modifier!r} needs a grain: it has no period to compare or reset against.",
            field="grain",
            allowed=allowed,
        )
        self.modifier = modifier


class NotAdditiveError(IntentError):
    """A running total was asked of a metric whose values cannot be summed across periods.

    Summing weekly voucher rates does not give a voucher rate, and summing average call
    durations does not give an average. ``allowed`` lists the metrics that can carry one.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.NOT_ADDITIVE

    def __init__(self, metric: str, allowed: list[str]) -> None:
        super().__init__(
            f"Metric {metric!r} cannot be accumulated: its values do not sum across periods.",
            field="accumulate",
            allowed=allowed,
        )
        self.metric = metric


class AccumulationResetError(IntentError):
    """A running total would reset on a period its buckets do not fall inside.

    Resetting monthly over weekly buckets has no honest answer: the week that straddles a
    month boundary belongs to both. Resetting on the grain itself is not a running total at
    all — every bucket would restart, which is just the ungrouped metric.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.ACCUMULATION_RESET

    def __init__(self, grain: str, reset: str, allowed: list[str]) -> None:
        detail = (
            "that is the bucket itself, so nothing accumulates"
            if grain == reset
            else f"a {grain} does not fall wholly inside a {reset}"
        )
        super().__init__(
            f"Cannot reset a {grain}ly running total on {reset!r}: {detail}.",
            field="accumulate",
            allowed=allowed,
        )
        self.grain = grain
        self.reset = reset


class PartialAccumulationError(IntentError):
    """A running total whose window starts after its reset period began.

    "Revenue year-to-date, for the last 90 days" reads as a year-to-date and is not one: the
    total starts at the range's first day, not January. The rows would be labelled exactly as
    the honest ones are, so refuse rather than answer a different question quietly.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.PARTIAL_ACCUMULATION

    def __init__(self, start: str, reset: str, boundary: str) -> None:
        super().__init__(
            f"A {reset}ly running total cannot start on {start}: the {reset} began on "
            f"{boundary}, so the first total would not be a {reset}-to-date.",
            field="date_range",
            allowed=[boundary],
        )
        self.boundary = boundary


class DateGroupByError(IntentError):
    """Bucketing a date and also grouping by that same raw date.

    "Monthly, by lead date" groups by month *and* by individual day, so each row is a single
    day wearing a month's label. One of the two is what the caller meant.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.DATE_GROUP_BY

    def __init__(self, dimension: str, grain: str, allowed: list[str]) -> None:
        super().__init__(
            f"Cannot group by {dimension!r} while bucketing it by {grain}: drop the grain to "
            f"see raw dates, or drop the dimension to see one row per {grain}.",
            field="group_by",
            allowed=allowed,
        )
        self.dimension = dimension


class CompareWithAccumulateError(IntentError):
    """Comparing a running total to the previous bucket's running total.

    Meaningful in principle, but it stacks one window function on another and needs a second
    subquery level. Nothing asks for it. Refuse it plainly rather than emit SQL no dialect
    agrees on.
    """

    code: ClassVar[IntentErrorCode] = IntentErrorCode.COMPARE_WITH_ACCUMULATE

    def __init__(self) -> None:
        super().__init__(
            "compare and accumulate cannot be combined in one intent.",
            field="compare",
            allowed=[],
        )


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
