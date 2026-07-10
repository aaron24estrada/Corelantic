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
