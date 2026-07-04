"""Typed models for the semantic layer.

The registry is the single source of truth for the business vocabulary that both the
deterministic dashboard and the agent draw on. It splits logical concepts from their
physical bindings along the four types the design rests on (see docs/concepts.md):

- **Entity** — the only type that binds a physical table or view (its ``source``).
- **Dimension** — a column (or expression) on an entity you can group or filter by.
- **Measure** — an aggregation over an entity, e.g. ``count(*)`` or ``sum(spend)``.
- **Metric** — a business-facing value built from measures, in one of five shapes
  (the taxonomy from docs/data-model.md, mirroring dbt MetricFlow):
  *simple* surfaces one measure; *ratio* divides two; *derived* is a formula over
  several; *cumulative* (MTD/YTD) and *comparison* (WoW/MoM) add time intelligence and
  are compiled by B4.

Logical concepts reference an entity or measure *by name* rather than carrying a table +
raw SQL inline. Entity ``source`` names and measure/dimension expressions are authored by
us; they are the trusted side of the SQL trust boundary (see app/query/compiler.py).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.semantic.errors import (
    UnknownDimensionError,
    UnknownEntityError,
    UnknownMeasureError,
    UnknownMetricError,
)


class SemanticModel(BaseModel):
    """Base for every registry model: unknown fields are a load-time error.

    Authoring mistakes — a misspelled key, or ratio fields on a metric that forgot
    ``type: ratio`` and defaulted to simple — fail loudly at load instead of being
    silently dropped. The registry is the trusted side of the SQL boundary; a definition
    that does not mean what it says must not load.
    """

    model_config = ConfigDict(extra="forbid")


class MetricFormat(StrEnum):
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENT = "percent"


class MetricType(StrEnum):
    SIMPLE = "simple"
    RATIO = "ratio"
    DERIVED = "derived"
    CUMULATIVE = "cumulative"
    COMPARISON = "comparison"


class Entity(SemanticModel):
    """A queryable table or view — the one place a physical binding lives."""

    name: str = Field(description="Stable identifier, referenced by dimensions and measures.")
    label: str = Field(description="Human-readable label for display.")
    source: str = Field(description="Physical table or view this entity binds to.")


class Dimension(SemanticModel):
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


class Measure(SemanticModel):
    """An aggregation over an entity — the aggregate side of a metric's definition."""

    name: str = Field(description="Stable identifier, referenced by metrics.")
    entity: str = Field(description="Name of the entity this measure aggregates over.")
    expression: str = Field(description="SQL aggregate expression, e.g. count(*) or sum(spend).")


class MetricBase(SemanticModel):
    """Fields every metric carries, regardless of how its value is composed."""

    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    description: str = Field(description="What the metric means, in business terms.")
    format: MetricFormat = Field(
        default=MetricFormat.NUMBER, description="How the value is formatted for display."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class SimpleMetric(MetricBase):
    """One measure, surfaced directly (e.g. new_leads = lead_count)."""

    type: Literal[MetricType.SIMPLE] = MetricType.SIMPLE
    measure: str = Field(description="Name of the measure this metric surfaces.")


class RatioMetric(MetricBase):
    """One measure divided by another (e.g. cost_per_lead = spend / leads)."""

    type: Literal[MetricType.RATIO] = MetricType.RATIO
    numerator: str = Field(description="Name of the measure on top of the ratio.")
    denominator: str = Field(description="Name of the measure on the bottom (guarded for zero).")


class DerivedMetric(MetricBase):
    """A formula over several measures (e.g. margin = (revenue - cost) / revenue)."""

    type: Literal[MetricType.DERIVED] = MetricType.DERIVED
    measures: list[str] = Field(
        min_length=1, description="Component measures the formula may reference by name."
    )
    expression: str = Field(
        description="Formula over the component measures: names, numbers, and + - * / only."
    )


class CumulativeMetric(MetricBase):
    """A measure accumulated over a time window (MTD/YTD). Compiled by B4."""

    type: Literal[MetricType.CUMULATIVE] = MetricType.CUMULATIVE
    measure: str = Field(description="Name of the measure to accumulate.")
    window: str = Field(description="Accumulation window, e.g. mtd or ytd (time intelligence: B4).")


class ComparisonMetric(MetricBase):
    """A measure compared to a prior period (WoW/MoM). Compiled by B4."""

    type: Literal[MetricType.COMPARISON] = MetricType.COMPARISON
    measure: str = Field(description="Name of the measure to compare across periods.")
    period: str = Field(description="Prior period to compare against, e.g. wow or mom.")
    kind: Literal["pct", "change"] = Field(
        default="pct", description="Percent change or absolute change (time intelligence: B4)."
    )


Metric = Annotated[
    SimpleMetric | RatioMetric | DerivedMetric | CumulativeMetric | ComparisonMetric,
    Field(discriminator="type"),
]

# Parses a raw metric body (with its `type` discriminator) into the right variant.
METRIC_ADAPTER: TypeAdapter[Metric] = TypeAdapter(Metric)


class SemanticRegistry(SemanticModel):
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
