"""The chart spec: a drawing, described without naming a drawing library.

``ResultSet`` says what the numbers *are*; this says how to *show* them. It is the fourth seam
(decisions.md D-6) and the only layer that knows a chart exists — nothing under
``app/semantic`` or ``app/query`` may import it. ECharts is an implementation detail behind it:
the web renders a spec through one adapter, and swapping libraries rewrites that adapter alone.

The spec **carries its data** rather than pointing back at ``ResultSet.rows``. That duplicates
the numbers within one response, and buys three things: the renderer becomes a pure adapter
with no knowledge of column roles, an agent answer is one self-contained drawing instruction,
and every pivot decision stays in Python under test. Clients must render ``series`` and never
reconcile it against ``rows`` — ``tests/services/test_chart.py`` pins the two together.
"""

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field

from app.semantic.models import MetricFormat

# The categorical palette has eight fixed hues (apps/web/src/app/globals.css). It is a contract,
# not a rendering detail: a ninth series would need a generated colour, and generated hues are
# where colourblind-safe palettes go to die. The builder refuses rather than invent one.
PALETTE_SLOTS: Final = 8


class ChartType(StrEnum):
    """What to draw. Extending the spec is how a new visual arrives, never a new component."""

    LINE = "line"
    BAR = "bar"


class SeriesRole(StrEnum):
    PRIMARY = "primary"
    # The metric's own earlier window (`previous`). Not another entity, so it takes its
    # primary's colour and is distinguished by stroke, never by hue.
    COMPARISON = "comparison"


class ChartRequest(BaseModel):
    """How the caller wants the answer drawn.

    Deliberately a sibling of ``QueryIntent`` and never a field on it: an intent is
    visual-independent (concepts.md §2), so `resolved_intent` must never echo a chart type back
    and the agent's planner must never have to choose one to ask a question.
    """

    type: ChartType = Field(description="The visual to render this result as.")


class ChartAxis(BaseModel):
    label: str = Field(description="Axis heading.")
    format: MetricFormat | None = Field(
        default=None, description="How to format tick labels; absent for categorical axes."
    )


class ChartSeries(BaseModel):
    name: str = Field(description="Legend entry: the metric's label, or a dimension member.")
    data: list[float | None] = Field(
        description=(
            "One value per entry in `categories`, in that order. `null` is a gap the renderer "
            "must break the line across, not a zero: a bucket with no rows, or the first "
            "bucket of a comparison, which has nothing before it."
        )
    )
    format: MetricFormat = Field(description="How to format this series' values.")
    role: SeriesRole = Field(description="Whether this is the metric or its earlier window.")
    palette_index: int = Field(
        ge=0,
        lt=PALETTE_SLOTS,
        description=(
            "Zero-based categorical slot, fixed to the *entity* this series names and never to "
            "its rank or its position in this particular result. Cross-filtering a chart down "
            "to three of its channels must not repaint them, so the index is the member's "
            "position in the registry's declared `members` — a property of the model, not of "
            "the data. A comparison series repeats its primary's index."
        ),
    )


class ChartSpec(BaseModel):
    type: ChartType
    title: str = Field(description="The metric being drawn.")
    subtitle: str | None = Field(
        default=None,
        description="The window actually covered, resolved from the intent. A caption, not a hint.",
    )
    categories: list[str] = Field(
        description="The categorical axis: ISO period starts, or dimension members."
    )
    x: ChartAxis
    y: ChartAxis
    series: list[ChartSeries] = Field(description="One entry per line or bar group.")
