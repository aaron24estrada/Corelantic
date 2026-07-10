"""The vocabulary, and what may be asked of it.

`docs/concepts.md` §3: the schema bounds the model and the model bounds the visuals. The
engine has always *enforced* that bound — a dimension that would fan out is refused — but
nothing published it, so a caller could only discover the shape of the model by asking wrong
questions and reading the errors.

This is that bound, made readable. The planner (E2) draws intents from it instead of inventing
names; the dashboard's controls (D6) populate themselves from it instead of hardcoding a list
that silently rots when a metric moves entity.

It bounds the *vocabulary*, not the shape of a request. Three refusals remain reachable from
catalog-only names, because each is a property of the question rather than of the model:
combining `compare` with `accumulate`, grouping by the very date `grain` is bucketing, and
starting a running total mid-period. Each 422 names its own repair.
"""

from pydantic import BaseModel, Field

from app.query.time import Grain, RelativeRange
from app.semantic.models import MetricFormat, MetricType


class MetricCapabilities(BaseModel):
    compare: bool = Field(
        description=(
            "Whether each bucket may be measured against the one before it. Needs a grain, "
            "which needs a date dimension this metric can reach."
        )
    )
    accumulate: bool = Field(
        description=(
            "Whether a running total is meaningful — true only when the metric's values sum "
            "across periods. A rate's do not."
        )
    )


class CatalogMetric(BaseModel):
    name: str = Field(description="Stable identifier; what an intent names.")
    label: str = Field(description="Human-readable label for display.")
    description: str = Field(description="What the metric means, in business terms.")
    type: MetricType = Field(description="How the value is composed: simple, ratio or derived.")
    format: MetricFormat = Field(description="How the value is formatted for display.")
    synonyms: list[str] = Field(description="Natural-language aliases that resolve to it.")
    groupable_dimensions: list[str] = Field(
        description=(
            "Every dimension this metric may be grouped or filtered by — one rule governs "
            "both. The others are not missing: they would fan out, are unrelated, or are "
            "pinned by the metric's own filter. A date dimension listed here may be grouped "
            "by, but not while `grain` is bucketing that same date."
        )
    )
    date_dimensions: list[str] = Field(
        description=(
            "The dates a time question about this metric may anchor on. More than one means "
            "an intent must name which; we never guess between date roles."
        )
    )
    supports: MetricCapabilities = Field(description="Which time modifiers this metric admits.")


class CatalogDimension(BaseModel):
    name: str = Field(description="Stable identifier; what an intent names.")
    label: str = Field(description="Human-readable label for display.")
    date_role: str | None = Field(
        default=None, description="Set when this is a date, naming its role (lead, referral)."
    )
    members: list[str] = Field(description="Known values, when the set is closed. Else empty.")
    synonyms: list[str] = Field(description="Natural-language aliases that resolve to it.")


class AccumulationRule(BaseModel):
    """Which periods a running total may reset on, for one bucket grain.

    A calendar fact, not an ordering: a week straddles a month boundary, so weekly buckets
    cannot reset monthly. `resets` is empty when nothing is coarser.
    """

    grain: Grain = Field(description="The bucket grain the intent asks for.")
    resets: list[Grain] = Field(description="Periods a running total over that grain may reset on.")


class CatalogResponse(BaseModel):
    metrics: list[CatalogMetric] = Field(description="Every metric, and what it can be asked.")
    dimensions: list[CatalogDimension] = Field(description="Every dimension in the model.")
    grains: list[Grain] = Field(description="Bucket sizes an intent may request.")
    relative_ranges: list[RelativeRange] = Field(
        description="Windows named relative to today, resolved server-side against one date."
    )
    # A list rather than a map keyed by Grain: OpenAPI cannot close the key set of an object,
    # so a dict reaches TypeScript as `{[key: string]: Grain[]}` and a typo in the grain goes
    # unchecked. As a list, both sides of the rule are typed.
    accumulation_resets: list[AccumulationRule] = Field(
        description="Per bucket grain, the periods a running total may reset on."
    )
