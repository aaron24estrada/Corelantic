from fastapi import APIRouter

from app.api.dependencies import DataSourceDep, RegistryDep
from app.query.intent import QueryIntent
from app.schemas.metric import MetricListResponse, MetricResultResponse, MetricSummary
from app.services.metrics import MetricsService

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


@router.get("/{metric_name}", response_model=MetricResultResponse)
async def get_metric(
    metric_name: str, registry: RegistryDep, data_source: DataSourceDep
) -> MetricResultResponse:
    registry.metric(metric_name)  # raises UnknownMetricError -> 404 if not defined
    service = MetricsService(registry=registry, data_source=data_source)
    rows = await service.compute(QueryIntent(metric=metric_name))
    return MetricResultResponse(name=metric_name, rows=rows)
