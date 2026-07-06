"""Compile a validated query intent into a SQLAlchemy Core statement.

This is the SQL trust boundary. Identifiers — the entity's source, measure aggregate
expressions, and dimension columns — come only from the registry, which we author, and
are placed into the statement as Core column/table clauses. The caller's untrusted
contribution is dimension *names* (validated against the registry, so an unknown name
raises rather than reaching SQL), filter *values*, and date-range *values* (never rendered
into the statement — Core binds them as parameters). Grain is a closed enum inlined during
compilation, not data. Because we return a Core expression tree rather than a string, value
parameterization is structural: there is no place a value could be concatenated.

Two shapes come out of here. Most metrics compile to a flat aggregate (``_compile_aggregate``),
optionally bucketed by a date grain and bounded by a range. Cumulative and comparison
metrics are inherently windowed (``_compile_temporal``): the measure is aggregated per date
bucket in a subquery, then a window function turns those buckets into a running total
(cumulative) or a prior-period delta (comparison). Grain truncation is a dialect-neutral
``DateBucket`` construct (see app/query/time); its SQL Server rendering ships with the C2
adapter. Scope is a single entity; cross-entity joins are B3.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    TableClause,
    column,
    func,
    literal_column,
    select,
    table,
)
from sqlalchemy.sql.selectable import Subquery

from app.query.errors import CrossEntityError, DateDimensionError
from app.query.formula import build_formula, safe_divide
from app.query.intent import QueryIntent
from app.query.time import DateBucket, DateRange, Grain
from app.semantic.models import (
    ComparisonMetric,
    ComparisonPeriod,
    CumulativeMetric,
    CumulativeWindow,
    DerivedMetric,
    Dimension,
    Entity,
    Measure,
    Metric,
    RatioMetric,
    SemanticRegistry,
    SimpleMetric,
)
from app.semantic.resolve import resolve_metric_entity

_PERIOD_GRAIN = {ComparisonPeriod.WOW: Grain.WEEK, ComparisonPeriod.MOM: Grain.MONTH}
_WINDOW_GRAIN = {CumulativeWindow.MTD: Grain.MONTH, CumulativeWindow.YTD: Grain.YEAR}


def compile_query(intent: QueryIntent, registry: SemanticRegistry) -> Select[Any]:
    metric = registry.metric(intent.metric)
    entity_name = resolve_metric_entity(metric, registry)
    entity = registry.entity(entity_name)

    if isinstance(metric, (ComparisonMetric, CumulativeMetric)):
        return _compile_temporal(metric, intent, entity_name, entity, registry)
    return _compile_aggregate(metric, intent, entity_name, entity, registry)


def _compile_aggregate(
    metric: Metric,
    intent: QueryIntent,
    entity_name: str,
    entity: Entity,
    registry: SemanticRegistry,
) -> Select[Any]:
    value_expr = _value_expression(metric, registry)
    group_dimensions = _group_dimensions(intent, entity_name, registry)

    date_dimension = None
    if intent.grain is not None or intent.date_range is not None:
        date_dimension = _resolve_date_dimension(intent, entity_name, registry)

    selected: list[ColumnElement[Any]] = []
    group_bys: list[ColumnElement[Any]] = []
    if intent.grain is not None:
        assert date_dimension is not None  # resolved above whenever grain is set
        bucket = DateBucket(intent.grain, column(date_dimension.column))
        selected.append(bucket.label("period"))
        group_bys.append(bucket)
    selected += [column(d.column).label(d.name) for d in group_dimensions]
    group_bys += [column(d.column) for d in group_dimensions]
    selected.append(value_expr.label(metric.name))

    statement = select(*selected).select_from(_source(entity))
    statement = _apply_where(statement, intent, entity_name, date_dimension, registry)
    if group_bys:
        statement = statement.group_by(*group_bys)
    return statement


def _compile_temporal(
    metric: ComparisonMetric | CumulativeMetric,
    intent: QueryIntent,
    entity_name: str,
    entity: Entity,
    registry: SemanticRegistry,
) -> Select[Any]:
    measure = registry.measure(metric.measure)
    date_dimension = _resolve_date_dimension(intent, entity_name, registry)
    group_dimensions = _group_dimensions(intent, entity_name, registry)

    bucket = DateBucket(_bucket_grain(metric, intent), column(date_dimension.column))
    inner: list[ColumnElement[Any]] = [bucket.label("period")]
    inner += [column(d.column).label(d.name) for d in group_dimensions]
    inner.append(literal_column(measure.expression).label("value"))

    aggregate = select(*inner).select_from(_source(entity))
    aggregate = _apply_where(aggregate, intent, entity_name, date_dimension, registry)
    aggregate = aggregate.group_by(bucket, *(column(d.column) for d in group_dimensions))
    sub = aggregate.subquery()

    delta = _window_value(metric, sub, group_dimensions)
    outer: list[ColumnElement[Any]] = [sub.c.period]
    outer += [sub.c[d.name] for d in group_dimensions]
    outer.append(delta.label(metric.name))
    return select(*outer).select_from(sub)


def _window_value(
    metric: ComparisonMetric | CumulativeMetric,
    sub: Subquery,
    group_dimensions: list[Dimension],
) -> ColumnElement[Any]:
    value = sub.c.value
    period = sub.c.period
    partition = [sub.c[d.name] for d in group_dimensions]

    if isinstance(metric, ComparisonMetric):
        # LAG compares to the previous *populated* bucket. With continuous data (daily
        # leads/spend) that is the prior calendar period; a fully empty week/month has no
        # row and would be skipped. Closing that gap needs a calendar spine joined to the
        # buckets — a DimDate join, which arrives with B3.
        prior = func.lag(value).over(partition_by=partition, order_by=period)
        if metric.kind == "pct":
            return safe_divide(value - prior, prior)
        return value - prior

    reset = DateBucket(_WINDOW_GRAIN[metric.window], period)
    return func.sum(value).over(partition_by=[reset, *partition], order_by=period, rows=(None, 0))


def _bucket_grain(metric: ComparisonMetric | CumulativeMetric, intent: QueryIntent) -> Grain:
    # Comparison's grain is fixed by its period (WoW is weekly); cumulative accumulates at
    # the requested grain, defaulting to daily.
    if isinstance(metric, ComparisonMetric):
        return _PERIOD_GRAIN[metric.period]
    return intent.grain or Grain.DAY


def _resolve_date_dimension(
    intent: QueryIntent, entity_name: str, registry: SemanticRegistry
) -> Dimension:
    if intent.date_dimension is not None:
        dimension = registry.dimension(intent.date_dimension)  # UnknownDimensionError if absent
        if dimension.date_role is None:
            raise DateDimensionError(entity_name, f"{dimension.name!r} is not a date dimension")
        if dimension.entity != entity_name:
            raise DateDimensionError(entity_name, f"{dimension.name!r} is on {dimension.entity!r}")
        return dimension

    temporal = [
        d
        for d in registry.dimensions.values()
        if d.date_role is not None and d.entity == entity_name
    ]
    if len(temporal) == 1:
        return temporal[0]
    if not temporal:
        raise DateDimensionError(entity_name, "the entity has no date dimension")
    names = sorted(d.name for d in temporal)
    raise DateDimensionError(entity_name, f"several date dimensions {names}; name one")


def _apply_where(
    statement: Select[Any],
    intent: QueryIntent,
    entity_name: str,
    date_dimension: Dimension | None,
    registry: SemanticRegistry,
) -> Select[Any]:
    for name, value in intent.filters.items():
        dimension = registry.dimension(name)
        _require_entity(entity_name, dimension)
        # Core binds the value as a parameter; it is never rendered into the SQL text.
        statement = statement.where(column(dimension.column) == value)
    if intent.date_range is not None:
        assert date_dimension is not None  # resolved whenever a range is set
        for condition in _range_conditions(date_dimension, intent.date_range):
            statement = statement.where(condition)
    return statement


def _range_conditions(date_dimension: Dimension, date_range: DateRange) -> list[ColumnElement[Any]]:
    date_column: ColumnElement[Any] = column(date_dimension.column)
    conditions: list[ColumnElement[Any]] = []
    if date_range.start is not None:
        conditions.append(date_column >= date_range.start)
    if date_range.end is not None:
        # Half-open upper bound: `< end + 1 day` includes all of the end date even when the
        # column is a timestamp (a plain `<= end` would drop rows after midnight that day).
        conditions.append(date_column < date_range.end + timedelta(days=1))
    return conditions


def _group_dimensions(
    intent: QueryIntent, entity_name: str, registry: SemanticRegistry
) -> list[Dimension]:
    dimensions = [registry.dimension(name) for name in intent.group_by]
    for dimension in dimensions:
        _require_entity(entity_name, dimension)
    return dimensions


def _value_expression(metric: Metric, registry: SemanticRegistry) -> ColumnElement[Any]:
    """The metric's value as a Core expression, dispatched on its (non-temporal) type."""

    if isinstance(metric, SimpleMetric):
        return _measure(registry.measure(metric.measure))
    if isinstance(metric, RatioMetric):
        numerator = _measure(registry.measure(metric.numerator))
        denominator = _measure(registry.measure(metric.denominator))
        return safe_divide(numerator, denominator)
    if isinstance(metric, DerivedMetric):
        # build_formula validates the expression (names must be in `measures`) before
        # translating it; resolve only maps an approved name to its measure expression.
        def resolve(name: str) -> ColumnElement[Any]:
            return _measure(registry.measure(name))

        return build_formula(metric.expression, set(metric.measures), resolve)
    # Temporal metrics are compiled by _compile_temporal, never here.
    raise AssertionError(f"non-aggregate metric reached _value_expression: {metric!r}")


def _measure(measure: Measure) -> ColumnElement[Any]:
    return literal_column(measure.expression)


def _source(entity: Entity) -> TableClause:
    """A Core table clause for the entity, splitting an optional ``schema.`` prefix."""

    schema, _, name = entity.source.rpartition(".")
    return table(name, schema=schema or None)


def _require_entity(entity: str, dimension: Dimension) -> None:
    if dimension.entity != entity:
        raise CrossEntityError(entity, dimension)
