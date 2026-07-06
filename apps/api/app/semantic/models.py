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

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

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


class CumulativeWindow(StrEnum):
    """The period a cumulative metric accumulates within before resetting."""

    MTD = "mtd"
    YTD = "ytd"


class ComparisonPeriod(StrEnum):
    """The prior period a comparison metric measures change against."""

    WOW = "wow"
    MOM = "mom"


class Aggregation(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class JoinEdge(SemanticModel):
    """A key relationship from one entity to another, an edge in the join graph.

    The compiler joins the dimension table in *before* aggregating, so an edge is expected
    to be many-to-one from the fact side — the target is a conformed dimension unique on
    its join key (geo, dim_date). A one-to-many edge would fan out and inflate the fact's
    measures; handling that safely (cardinality-aware pre-aggregation) is a follow-up, so
    for now only declare many-to-one/one-to-one edges.
    """

    to: str = Field(description="Name of the entity this edge joins to.")
    left: str = Field(description="Join-key column on this entity.")
    right: str = Field(description="Join-key column on the target entity (unique per row).")


class Entity(SemanticModel):
    """A queryable table or view — the one place a physical binding lives."""

    name: str = Field(description="Stable identifier, referenced by dimensions and measures.")
    label: str = Field(description="Human-readable label for display.")
    source: str = Field(description="Physical table or view this entity binds to.")
    joins: list[JoinEdge] = Field(
        default_factory=list,
        description="Key relationships to other entities; edges the compiler joins along.",
    )


class Dimension(SemanticModel):
    name: str = Field(description="Stable identifier, referenced by intents and visuals.")
    label: str = Field(description="Human-readable label for display.")
    entity: str = Field(description="Name of the entity this dimension is read from.")
    column: str = Field(
        description="Column on the entity that holds the value; an identifier, bound to its table."
    )
    date_role: str | None = Field(
        default=None,
        description=(
            "If set, a date dimension of this role (e.g. lead, referral) — its column is a "
            "date the compiler may bucket by grain and filter by range. There are two roles "
            "(lead vs referral); an intent names which one to use."
        ),
    )
    members: list[str] = Field(
        default_factory=list, description="Known values, when the set is closed."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Natural-language aliases used for matching."
    )


class Measure(SemanticModel):
    """An aggregation over one column of an entity — the aggregate side of a metric.

    Structured rather than raw SQL (``agg`` + ``column``) so the compiler binds the column
    to its table and qualifies it: in a joined query ``count(distinct LeadId)`` is
    unambiguous by construction, and the aggregate is a function from a closed set over a
    named column, never an opaque SQL fragment.
    """

    name: str = Field(description="Stable identifier, referenced by metrics.")
    entity: str = Field(description="Name of the entity this measure aggregates over.")
    agg: Aggregation = Field(description="The aggregate function to apply.")
    column: str | None = Field(
        default=None,
        description="Column to aggregate; omit only for count (count of rows).",
    )
    distinct: bool = Field(
        default=False, description="Aggregate distinct values (e.g. count of distinct ids)."
    )

    @model_validator(mode="after")
    def _needs_a_column(self) -> "Measure":
        if self.agg is not Aggregation.COUNT and self.column is None:
            raise ValueError(f"measure {self.name!r}: {self.agg.value} requires a column")
        if self.distinct and self.column is None:
            raise ValueError(f"measure {self.name!r}: distinct requires a column")
        return self


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
    window: CumulativeWindow = Field(description="Period the running total resets within.")


class ComparisonMetric(MetricBase):
    """A measure compared to a prior period (WoW/MoM)."""

    type: Literal[MetricType.COMPARISON] = MetricType.COMPARISON
    measure: str = Field(description="Name of the measure to compare across periods.")
    period: ComparisonPeriod = Field(description="Prior period to compare against.")
    kind: Literal["pct", "change"] = Field(
        default="pct", description="Percent change or absolute change."
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
