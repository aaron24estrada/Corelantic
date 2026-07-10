from fastapi import APIRouter

from app.api.dependencies import RegistryDep
from app.schemas.metric import MetricListResponse, MetricSummary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricListResponse)
async def list_metrics(registry: RegistryDep) -> MetricListResponse:
    summaries = [
        MetricSummary(
            name=metric.name,
            label=metric.label,
            description=metric.description,
            format=metric.format,
        )
        for metric in registry.metrics.values()
    ]
    return MetricListResponse(metrics=summaries)
