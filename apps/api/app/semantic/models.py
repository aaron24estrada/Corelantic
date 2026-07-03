"""Typed models for the semantic layer.

The registry is the single source of truth for the business vocabulary — metrics and
dimensions — that both the deterministic dashboard and the agent draw on. Metric
expressions and source names live here and are authored by us; they are the trusted
side of the SQL trust boundary (see app/query/compiler.py).
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.semantic.errors import UnknownDimensionError, UnknownMetricError


class MetricFormat(StrEnum):
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENT = "percent"


class Dimension(BaseModel):
    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    source: str = Field(description="Table or view the dimension is read from.")
    column: str = Field(description="Column in the source that holds the value.")
    members: list[str] = Field(
        default_factory=list, description="Known values, when the set is closed."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class Metric(BaseModel):
    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    description: str = Field(description="What the metric means, in business terms.")
    source: str = Field(description="Table or view the metric is aggregated from.")
    expression: str = Field(description="SQL aggregate expression, e.g. count(*).")
    format: MetricFormat = Field(
        default=MetricFormat.NUMBER, description="How the value is formatted for display."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class SemanticRegistry(BaseModel):
    metrics: dict[str, Metric] = Field(default_factory=dict)
    dimensions: dict[str, Dimension] = Field(default_factory=dict)

    def metric(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError:
            raise UnknownMetricError(name) from None

    def dimension(self, name: str) -> Dimension:
        try:
            return self.dimensions[name]
        except KeyError:
            raise UnknownDimensionError(name) from None
