from pydantic import BaseModel, Field

from app.semantic.models import MetricFormat


class MetricSummary(BaseModel):
    name: str = Field(description="Stable identifier for the metric.")
    label: str = Field(description="Human-readable label for display.")
    description: str = Field(description="What the metric means, in business terms.")
    format: MetricFormat = Field(description="How the value is formatted for display.")


class MetricListResponse(BaseModel):
    metrics: list[MetricSummary] = Field(description="Metrics defined in the semantic registry.")


class MetricResultResponse(BaseModel):
    name: str = Field(description="The metric that was computed.")
    rows: list[dict[str, object]] = Field(
        description="Result rows; grouped dimensions and the metric value per row."
    )
