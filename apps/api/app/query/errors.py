"""Errors raised while compiling a query intent into SQL."""

from app.semantic.models import Dimension, Metric


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


class FormulaError(CompileError):
    """A derived metric's formula is not a supported expression.

    Formulas are a tiny language — component-measure names, numeric literals, and the
    binary operators ``+ - * /`` — parsed into a Core expression tree. Anything else
    (calls, attributes, an unknown measure name) is rejected rather than executed.
    """

    def __init__(self, expression: str, reason: str) -> None:
        super().__init__(f"Invalid formula {expression!r}: {reason}.")
        self.expression = expression
        self.reason = reason


class TimeIntelligenceRequiredError(CompileError):
    """A metric type needs time intelligence the MVP compiler does not have yet.

    Cumulative (MTD/YTD) and comparison (WoW/MoM) metrics need a date dimension, grain,
    and period-offset windowing — delivered by B4. They are modelled and validated now,
    but compiling them is deferred rather than faked.
    """

    def __init__(self, metric: Metric) -> None:
        super().__init__(
            f"Metric {metric.name!r} of type {metric.type.value!r} needs time "
            f"intelligence (B4) to compile."
        )
        self.metric = metric
