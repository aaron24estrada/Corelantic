"""The shape of a query's answer.

Rows alone are not an answer: nothing in ``{"period": ..., "voucher_rate": 0.24}`` says which
column is the measure, which is a dimension, or that the number is a rate and not a count.
Every caller would re-derive that from the intent, and the two would eventually disagree.
``ResultSet`` carries the column schema alongside the rows, so a chart, a table and a
narrative all read the same description.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.query.intent import QueryIntent
from app.query.rows import CellValue
from app.schemas.chart import ChartRequest, ChartSpec
from app.semantic.models import MetricFormat


class ColumnRole(StrEnum):
    PERIOD = "period"
    DIMENSION = "dimension"
    METRIC = "metric"
    PREVIOUS = "previous"
    DELTA = "delta"


class Column(BaseModel):
    name: str = Field(description="Key this column takes in every row.")
    role: ColumnRole = Field(description="What the column is for: an axis, a value, a change.")
    label: str = Field(description="Human-readable heading.")
    format: MetricFormat | None = Field(
        default=None, description="How to format the value; absent for periods and dimensions."
    )


class ResultSet(BaseModel):
    columns: list[Column] = Field(description="Describes each key in `rows`, in select order.")
    rows: list[dict[str, CellValue]] = Field(description="One row per group.")
    resolved_intent: QueryIntent = Field(
        description=(
            "The intent as it was actually run: a relative window resolved to explicit dates, "
            "the inferred date dimension named, the comparison's kind decided. A caption can "
            "state the window the chart truly covers."
        )
    )


class QueryRequest(BaseModel):
    """An intent, and optionally how to draw its answer.

    ``chart`` is a sibling of the intent and never a field on it. An intent is a question and is
    visual-independent (concepts.md §2); folding a chart type into it would echo presentation
    back through ``resolved_intent`` and force the agent's planner to pick a visual in order to
    ask anything at all.
    """

    intent: QueryIntent
    chart: ChartRequest | None = Field(
        default=None, description="Omit for rows only; name a type to also get a `ChartSpec`."
    )


class QueryResponse(BaseModel):
    result: ResultSet
    chart: ChartSpec | None = Field(
        default=None, description="Present exactly when the request asked for a chart."
    )
