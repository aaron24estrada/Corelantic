"""Compile a validated query intent into a SQLAlchemy Core statement.

This is the SQL trust boundary. Every identifier — table sources, the columns measures
and dimensions name, join keys — comes only from the registry, which we author, and is
placed into the statement as a Core clause bound to its table. The caller's untrusted
contribution is dimension/metric *names* (validated against the registry) and filter and
date-range *values* (bound as parameters, never rendered). Grain is a closed enum inlined
at compile time. Because we return a Core expression tree, value parameterization is
structural: there is no place a value could be concatenated.

A metric aggregates one fact entity, but its group-by dimensions may live on other
entities. ``_build_plan`` finds the join path from the fact entity to each and builds an
aliased, joined FROM; every column is then referenced through its entity's alias
(``plan.col(entity, column)``), so a joined query is unambiguous by construction. Most
metrics compile to a flat aggregate; cumulative and comparison metrics are windowed over a
per-bucket subquery (see ``_compile_temporal``). Grain truncation is the dialect-neutral
``DateBucket`` (app/query/time); its SQL Server rendering ships with the C2 adapter.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    case,
    column,
    distinct,
    func,
    literal,
    select,
    table,
)
from sqlalchemy.sql.selectable import FromClause, NamedFromClause, Subquery

from app.query.errors import DateDimensionError, FilteredMeasureConflictError
from app.query.formula import build_formula, safe_divide
from app.query.intent import QueryIntent
from app.query.time import DateBucket, DateRange, Grain
from app.semantic.errors import JoinFanOutError
from app.semantic.joins import JoinStep, find_join_path
from app.semantic.models import (
    Aggregation,
    ComparisonMetric,
    ComparisonPeriod,
    CumulativeMetric,
    CumulativeWindow,
    DerivedMetric,
    Dimension,
    Measure,
    Metric,
    RatioMetric,
    SemanticRegistry,
    SimpleMetric,
)
from app.semantic.resolve import measure_names, resolve_metric_entity

_PERIOD_GRAIN = {ComparisonPeriod.WOW: Grain.WEEK, ComparisonPeriod.MOM: Grain.MONTH}
_WINDOW_GRAIN = {CumulativeWindow.MTD: Grain.MONTH, CumulativeWindow.YTD: Grain.YEAR}


@dataclass(frozen=True)
class _Plan:
    """The aliased tables of a query and the joined FROM built over them."""

    tables: dict[str, NamedFromClause]
    from_clause: FromClause

    def col(self, entity: str, column_name: str) -> ColumnElement[Any]:
        return self.tables[entity].c[column_name]


def compile_query(intent: QueryIntent, registry: SemanticRegistry) -> Select[Any]:
    metric = registry.metric(intent.metric)
    base = resolve_metric_entity(metric, registry)

    if isinstance(metric, (ComparisonMetric, CumulativeMetric)):
        return _compile_temporal(metric, intent, base, registry)
    return _compile_aggregate(metric, intent, base, registry)


def _compile_aggregate(
    metric: Metric, intent: QueryIntent, base: str, registry: SemanticRegistry
) -> Select[Any]:
    group_dimensions = [registry.dimension(name) for name in intent.group_by]
    filter_dimensions = {name: registry.dimension(name) for name in intent.filters}
    date_dimension = None
    if intent.grain is not None or intent.date_range is not None:
        date_dimension = _resolve_date_dimension(intent, base, registry)

    references = _references(
        metric, group_dimensions, list(filter_dimensions.values()), date_dimension, registry
    )
    plan = _build_plan(base, references, registry)

    value_expr = _value_expression(metric, registry, plan)
    selected: list[ColumnElement[Any]] = []
    group_bys: list[ColumnElement[Any]] = []
    if intent.grain is not None:
        assert date_dimension is not None  # resolved above whenever grain is set
        bucket = DateBucket(intent.grain, plan.col(date_dimension.entity, date_dimension.column))
        selected.append(bucket.label("period"))
        group_bys.append(bucket)
    for dimension in group_dimensions:
        col = plan.col(dimension.entity, dimension.column)
        selected.append(col.label(dimension.name))
        group_bys.append(col)
    selected.append(value_expr.label(metric.name))

    statement = select(*selected).select_from(plan.from_clause)
    statement = _apply_where(statement, intent, filter_dimensions, date_dimension, plan)
    if group_bys:
        statement = statement.group_by(*group_bys)
    return statement


def _compile_temporal(
    metric: ComparisonMetric | CumulativeMetric,
    intent: QueryIntent,
    base: str,
    registry: SemanticRegistry,
) -> Select[Any]:
    measure = registry.measure(metric.measure)
    filter_dimensions = {name: registry.dimension(name) for name in intent.filters}
    group_dimensions = [registry.dimension(name) for name in intent.group_by]
    date_dimension = _resolve_date_dimension(intent, base, registry)

    references = _references(
        metric, group_dimensions, list(filter_dimensions.values()), date_dimension, registry
    )
    plan = _build_plan(base, references, registry)

    bucket = DateBucket(
        _bucket_grain(metric, intent), plan.col(date_dimension.entity, date_dimension.column)
    )
    inner: list[ColumnElement[Any]] = [bucket.label("period")]
    inner += [plan.col(d.entity, d.column).label(d.name) for d in group_dimensions]
    inner.append(_measure_expression(measure, plan).label("value"))

    aggregate = select(*inner).select_from(plan.from_clause)
    aggregate = _apply_where(aggregate, intent, filter_dimensions, date_dimension, plan)
    aggregate = aggregate.group_by(
        bucket, *(plan.col(d.entity, d.column) for d in group_dimensions)
    )
    sub = aggregate.subquery()

    delta = _window_value(metric, sub, group_dimensions)
    outer: list[ColumnElement[Any]] = [sub.c.period]
    outer += [sub.c[d.name] for d in group_dimensions]
    outer.append(delta.label(metric.name))
    return select(*outer).select_from(sub)


def _references(
    metric: Metric,
    group_dimensions: list[Dimension],
    filter_dimensions: list[Dimension],
    date_dimension: Dimension | None,
    registry: SemanticRegistry,
) -> dict[str, set[str]]:
    """Columns referenced per entity, before join keys are added by ``_build_plan``."""

    references: dict[str, set[str]] = {}

    def add(entity: str, column_name: str | None) -> None:
        references.setdefault(entity, set())
        if column_name is not None:
            references[entity].add(column_name)

    sliced = [*group_dimensions, *filter_dimensions]
    for name in measure_names(metric):
        measure = registry.measure(name)
        add(measure.entity, measure.column)
        if measure.filter is not None:
            add(measure.entity, measure.filter.column)
            _reject_slicing_a_filtered_column(metric, measure, sliced)
    for dimension in sliced:
        add(dimension.entity, dimension.column)
    if date_dimension is not None:
        add(date_dimension.entity, date_dimension.column)
    return references


def _reject_slicing_a_filtered_column(
    metric: Metric, measure: Measure, sliced: list[Dimension]
) -> None:
    assert measure.filter is not None
    for dimension in sliced:
        if dimension.entity == measure.entity and dimension.column == measure.filter.column:
            raise FilteredMeasureConflictError(metric.name, dimension.name)


def _build_plan(base: str, references: dict[str, set[str]], registry: SemanticRegistry) -> _Plan:
    columns = {entity: set(cols) for entity, cols in references.items()}
    columns.setdefault(base, set())

    steps: list[JoinStep] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entity in list(columns):
        for step in find_join_path(base, entity, registry):
            if step.fans_out:
                # Joining before aggregation would multiply the fact rows and inflate the
                # metric; reject rather than return silently-wrong numbers.
                raise JoinFanOutError(step.from_entity, step.to_entity)
            key = (step.from_entity, step.from_column, step.to_entity, step.to_column)
            if key not in seen:
                seen.add(key)
                steps.append(step)
    for step in steps:
        columns.setdefault(step.from_entity, set()).add(step.from_column)
        columns.setdefault(step.to_entity, set()).add(step.to_column)

    tables: dict[str, NamedFromClause] = {}
    for entity, cols in columns.items():
        source = registry.entity(entity).source
        schema, _, name = source.rpartition(".")
        clause = table(name, *(column(c) for c in sorted(cols)), schema=schema or None)
        tables[entity] = clause.alias(entity)

    from_clause: FromClause = tables[base]
    for step in steps:
        # Outer, not inner: facts with no dimension row (e.g. leads lacking geo) must
        # survive. Safe because fan-out hops are already rejected above.
        from_clause = from_clause.join(
            tables[step.to_entity],
            tables[step.from_entity].c[step.from_column]
            == tables[step.to_entity].c[step.to_column],
            isouter=True,
        )
    return _Plan(tables=tables, from_clause=from_clause)


def _value_expression(
    metric: Metric, registry: SemanticRegistry, plan: _Plan
) -> ColumnElement[Any]:
    """The metric's value as a Core expression, dispatched on its (non-temporal) type."""

    if isinstance(metric, SimpleMetric):
        return _measure_expression(registry.measure(metric.measure), plan)
    if isinstance(metric, RatioMetric):
        numerator = _measure_expression(registry.measure(metric.numerator), plan)
        denominator = _measure_expression(registry.measure(metric.denominator), plan)
        return safe_divide(numerator, denominator)
    if isinstance(metric, DerivedMetric):
        # build_formula validates the expression (names must be in `measures`) before
        # translating it; resolve maps an approved name to its measure expression.
        def resolve(name: str) -> ColumnElement[Any]:
            return _measure_expression(registry.measure(name), plan)

        return build_formula(metric.expression, set(metric.measures), resolve)
    # Temporal metrics are compiled by _compile_temporal, never here.
    raise AssertionError(f"non-aggregate metric reached _value_expression: {metric!r}")


def _measure_expression(measure: Measure, plan: _Plan) -> ColumnElement[Any]:
    if measure.column is None:
        if measure.filter is None:
            return func.count()  # count(*)
        return func.count(case((_filter_predicate(measure, plan), literal(1))))
    col = plan.col(measure.entity, measure.column)
    if measure.filter is not None:
        # NULL outside the predicate so those rows drop from the aggregate — a portable
        # partial aggregate (SQL Server has no FILTER clause).
        col = case((_filter_predicate(measure, plan), col))
    if measure.distinct:
        col = distinct(col)
    if measure.agg is Aggregation.COUNT:
        return func.count(col)
    if measure.agg is Aggregation.SUM:
        return func.sum(col)
    if measure.agg is Aggregation.AVG:
        return func.avg(col)
    if measure.agg is Aggregation.MIN:
        return func.min(col)
    return func.max(col)  # Aggregation.MAX


def _filter_predicate(measure: Measure, plan: _Plan) -> ColumnElement[bool]:
    assert measure.filter is not None
    # Identifier from the registry, value bound as a parameter (never interpolated).
    return plan.col(measure.entity, measure.filter.column) == measure.filter.equals


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
        # buckets — a DimDate join, a natural extension now that joins exist.
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
    intent: QueryIntent, base: str, registry: SemanticRegistry
) -> Dimension:
    if intent.date_dimension is not None:
        dimension = registry.dimension(intent.date_dimension)  # UnknownDimensionError if absent
        if dimension.date_role is None:
            raise DateDimensionError(base, f"{dimension.name!r} is not a date dimension")
        if dimension.entity != base:
            raise DateDimensionError(base, f"{dimension.name!r} is on {dimension.entity!r}")
        return dimension

    temporal = [
        d for d in registry.dimensions.values() if d.date_role is not None and d.entity == base
    ]
    if len(temporal) == 1:
        return temporal[0]
    if not temporal:
        raise DateDimensionError(base, "the entity has no date dimension")
    names = sorted(d.name for d in temporal)
    raise DateDimensionError(base, f"several date dimensions {names}; name one")


def _apply_where(
    statement: Select[Any],
    intent: QueryIntent,
    filter_dimensions: dict[str, Dimension],
    date_dimension: Dimension | None,
    plan: _Plan,
) -> Select[Any]:
    for name, value in intent.filters.items():
        dimension = filter_dimensions[name]
        # Core binds the value as a parameter; it is never rendered into the SQL text.
        statement = statement.where(plan.col(dimension.entity, dimension.column) == value)
    if intent.date_range is not None:
        assert date_dimension is not None  # resolved whenever a range is set
        for condition in _range_conditions(plan, date_dimension, intent.date_range):
            statement = statement.where(condition)
    return statement


def _range_conditions(
    plan: _Plan, date_dimension: Dimension, date_range: DateRange
) -> list[ColumnElement[Any]]:
    date_column = plan.col(date_dimension.entity, date_dimension.column)
    conditions: list[ColumnElement[Any]] = []
    if date_range.start is not None:
        conditions.append(date_column >= date_range.start)
    if date_range.end is not None:
        # Half-open upper bound: `< end + 1 day` includes all of the end date even when the
        # column is a timestamp (a plain `<= end` would drop rows after midnight that day).
        conditions.append(date_column < date_range.end + timedelta(days=1))
    return conditions
