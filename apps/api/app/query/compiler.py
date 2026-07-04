"""Compile a validated query intent into a SQLAlchemy Core statement.

This is the SQL trust boundary. Identifiers — the entity's source, measure aggregate
expressions, and dimension columns — come only from the registry, which we author, and
are placed into the statement as Core column/table clauses. The caller's untrusted
contribution is dimension *names* (validated against the registry, so an unknown name
raises rather than reaching SQL) and filter *values* (never rendered into the statement —
Core binds them as parameters). Because we return a Core expression tree rather than a
string, value parameterization is structural: there is no place a value could be
concatenated, so there is no injection surface.

The metric's *type* decides how its value expression is built (see app/semantic/models):
*simple* surfaces one measure, *ratio* divides two (guarded for zero), *derived* is a
formula over several. All component measures must share one entity, which supplies the
FROM. *Cumulative* and *comparison* need time intelligence and are deferred to B4. Scope
is aggregate + group-by + equality filters on a single entity; joins and time-grain
bucketing arrive with the real schema (docs O-2, epics B3/B4).
"""

from typing import Any, assert_never

from sqlalchemy import ColumnElement, Select, TableClause, column, literal_column, select, table

from app.query.errors import CrossEntityError, TimeIntelligenceRequiredError
from app.query.formula import build_formula, safe_divide
from app.query.intent import QueryIntent
from app.semantic.models import (
    ComparisonMetric,
    CumulativeMetric,
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


def compile_query(intent: QueryIntent, registry: SemanticRegistry) -> Select[Any]:
    metric = registry.metric(intent.metric)
    entity_name = resolve_metric_entity(metric, registry)
    value_expr = _value_expression(metric, registry)
    entity = registry.entity(entity_name)

    group_dimensions = [registry.dimension(name) for name in intent.group_by]
    for dimension in group_dimensions:
        _require_entity(entity_name, dimension)

    selected: list[ColumnElement[Any]] = [
        column(dimension.column).label(dimension.name) for dimension in group_dimensions
    ]
    selected.append(value_expr.label(metric.name))

    statement = select(*selected).select_from(_source(entity))

    for name, value in intent.filters.items():
        dimension = registry.dimension(name)
        _require_entity(entity_name, dimension)
        # Core binds the value as a parameter; it is never rendered into the SQL text.
        statement = statement.where(column(dimension.column) == value)

    if group_dimensions:
        statement = statement.group_by(*(column(d.column) for d in group_dimensions))

    return statement


def _value_expression(metric: Metric, registry: SemanticRegistry) -> ColumnElement[Any]:
    """The metric's value as a Core expression, dispatched on its type."""

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
    if isinstance(metric, (CumulativeMetric, ComparisonMetric)):
        raise TimeIntelligenceRequiredError(metric)
    assert_never(metric)


def _measure(measure: Measure) -> ColumnElement[Any]:
    return literal_column(measure.expression)


def _source(entity: Entity) -> TableClause:
    """A Core table clause for the entity, splitting an optional ``schema.`` prefix."""

    schema, _, name = entity.source.rpartition(".")
    return table(name, schema=schema or None)


def _require_entity(entity: str, dimension: Dimension) -> None:
    if dimension.entity != entity:
        raise CrossEntityError(entity, dimension)
