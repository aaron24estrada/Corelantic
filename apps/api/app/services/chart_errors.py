"""Errors raised when a result cannot honestly be drawn the way the caller asked.

Like ``app/query/errors.py`` these are the *caller's* mistake and map to 422 with ``allowed`` —
the vocabulary that would have worked — so the agent repairs its request and the dashboard's
error state names the options. Unlike those, they are faults of the *chart request*, not of the
intent: the intent is visual-independent and a chart type is not part of it (concepts.md §2).
That is why ``ChartError`` does not subclass ``IntentError`` — a chart fault must never be
reported against an intent field the caller never sent.
"""

from enum import StrEnum
from typing import ClassVar

from app.schemas.chart import ChartType


class ChartErrorCode(StrEnum):
    UNSUPPORTED_CHART_TYPE = "unsupported_chart_type"
    UNPIVOTABLE_DIMENSION = "unpivotable_dimension"


class ChartError(Exception):
    """Base for chart-request failures. ``code`` is stable; the message is not."""

    code: ClassVar[ChartErrorCode]

    def __init__(self, message: str, *, field: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.field = field
        self.allowed = allowed


class UnsupportedChartTypeError(ChartError):
    """The requested visual cannot draw the shape this intent returns.

    A line needs a period to run along; bars need exactly one categorical axis. The remedy is
    always the same — pick a type from ``allowed``, or change the intent's grain or group_by.
    """

    code: ClassVar[ChartErrorCode] = ChartErrorCode.UNSUPPORTED_CHART_TYPE

    def __init__(self, chart_type: ChartType, reason: str, allowed: list[ChartType]) -> None:
        super().__init__(
            f"Cannot draw this result as a {chart_type.value}: {reason}.",
            field="chart",
            allowed=[t.value for t in allowed],
        )
        self.chart_type = chart_type


class PivotNotSupportedError(ChartError):
    """A time series was grouped by a dimension whose members cannot each hold a colour.

    Splitting a trend into one line per member spends the categorical palette, and a series'
    colour must belong to the member rather than to its rank — otherwise cross-filtering a
    chart down to three channels repaints the three that remain, and the reader silently
    re-learns the legend. So a member's colour is its position in the registry's declared
    ``members``, which requires that list to exist and to fit the palette.

    Three causes, one remedy — pick a dimension from ``allowed``, or filter this one down to a
    single member and drop it from ``group_by``:

    *No declared members* (``state``, ``status``): the value set is open, so there is no
    position to key a colour on.
    *More members than colours* (``channel``, nine): two series would share a hue.
    *An undeclared value in the data*: the registry and the warehouse disagree; that is worth
    surfacing rather than painting grey.
    """

    code: ClassVar[ChartErrorCode] = ChartErrorCode.UNPIVOTABLE_DIMENSION

    def __init__(self, dimension: str, reason: str, allowed: list[str]) -> None:
        super().__init__(
            f"Cannot split a trend by dimension {dimension!r}: {reason}.",
            field="group_by",
            allowed=allowed,
        )
        self.dimension = dimension
