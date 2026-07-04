"""Typed models for the semantic layer.

The registry is the single source of truth for the business vocabulary that both the
deterministic dashboard and the agent draw on. It splits logical concepts from their
physical bindings along the four types the design rests on (see docs/concepts.md):

- **Entity** — the only type that binds a physical table or view (its ``source``).
- **Dimension** — a column (or expression) on an entity you can group or filter by.
- **Measure** — an aggregation over an entity, e.g. ``count(*)`` or ``sum(spend)``.
- **Metric** — a business-facing measure, carrying its label/format/synonyms.

Logical concepts (Dimension, Measure, Metric) reference an entity or measure *by name*
rather than carrying a table + raw SQL inline. Entity ``source`` names and measure/
dimension expressions are authored by us; they are the trusted side of the SQL trust
boundary (see app/query/compiler.py).
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.semantic.errors import (
    UnknownDimensionError,
    UnknownEntityError,
    UnknownMeasureError,
    UnknownMetricError,
)


class MetricFormat(StrEnum):
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENT = "percent"


class Entity(BaseModel):
    """A queryable table or view — the one place a physical binding lives."""

    name: str = Field(description="Stable identifier, referenced by dimensions and measures.")
    label: str = Field(description="Human-readable label for display.")
    source: str = Field(description="Physical table or view this entity binds to.")


class Dimension(BaseModel):
    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    entity: str = Field(description="Name of the entity this dimension is read from.")
    column: str = Field(description="Column (or expression) on the entity that holds the value.")
    members: list[str] = Field(
        default_factory=list, description="Known values, when the set is closed."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class Measure(BaseModel):
    """An aggregation over an entity — the aggregate side of a metric's definition."""

    name: str = Field(description="Stable identifier, referenced by metrics.")
    label: str = Field(description="Human-readable label for display.")
    entity: str = Field(description="Name of the entity this measure aggregates over.")
    expression: str = Field(description="SQL aggregate expression, e.g. count(*) or sum(spend).")


class Metric(BaseModel):
    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    description: str = Field(description="What the metric means, in business terms.")
    measure: str = Field(description="Name of the measure this metric surfaces.")
    format: MetricFormat = Field(
        default=MetricFormat.NUMBER, description="How the value is formatted for display."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class SemanticRegistry(BaseModel):
    entities: dict[str, Entity] = Field(default_factory=dict)
    dimensions: dict[str, Dimension] = Field(default_factory=dict)
    measures: dict[str, Measure] = Field(default_factory=dict)
    metrics: dict[str, Metric] = Field(default_factory=dict)

    def entity(self, name: str) -> Entity:
        try:
            return self.entities[name]
        except KeyError:
            raise UnknownEntityError(name) from None

    def dimension(self, name: str) -> Dimension:
        try:
            return self.dimensions[name]
        except KeyError:
            raise UnknownDimensionError(name) from None

    def measure(self, name: str) -> Measure:
        try:
            return self.measures[name]
        except KeyError:
            raise UnknownMeasureError(name) from None

    def metric(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError:
            raise UnknownMetricError(name) from None
