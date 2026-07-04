"""Compile a validated query intent into a SQLAlchemy Core statement.

This is the SQL trust boundary. Identifiers — the entity's source, the measure's
aggregate expression, and dimension columns — come only from the registry, which we
author, and are placed into the statement as Core column/table clauses. The caller's
untrusted contribution is dimension *names* (validated against the registry, so an
unknown name raises rather than reaching SQL) and filter *values* (never rendered into
the statement — Core binds them as parameters). Because we return a Core expression tree
rather than a string, value parameterization is structural: there is no place a value
could be concatenated, so there is no injection surface.

A metric resolves to its measure, and the measure to its entity: the entity supplies the
FROM, the measure the aggregate, the metric only the output name. The MVP scope is
aggregate + group-by + equality filters on a single entity. Time-grain bucketing and
cross-entity joins arrive with the real schema (docs O-2).
"""

from typing import Any

from sqlalchemy import ColumnElement, Select, TableClause, column, literal_column, select, table

from app.query.errors import CrossEntityError
from app.query.intent import QueryIntent
from app.semantic.models import Dimension, Entity, Measure, SemanticRegistry


def compile_query(intent: QueryIntent, registry: SemanticRegistry) -> Select[Any]:
    metric = registry.metric(intent.metric)
    measure = registry.measure(metric.measure)
    entity = registry.entity(measure.entity)

    group_dimensions = [registry.dimension(name) for name in intent.group_by]
    for dimension in group_dimensions:
        _require_same_entity(measure, dimension)

    selected: list[ColumnElement[Any]] = [
        column(dimension.column).label(dimension.name) for dimension in group_dimensions
    ]
    selected.append(literal_column(measure.expression).label(metric.name))

    statement = select(*selected).select_from(_source(entity))

    for name, value in intent.filters.items():
        dimension = registry.dimension(name)
        _require_same_entity(measure, dimension)
        # Core binds the value as a parameter; it is never rendered into the SQL text.
        statement = statement.where(column(dimension.column) == value)

    if group_dimensions:
        statement = statement.group_by(*(column(d.column) for d in group_dimensions))

    return statement


def _source(entity: Entity) -> TableClause:
    """A Core table clause for the entity, splitting an optional ``schema.`` prefix."""

    schema, _, name = entity.source.rpartition(".")
    return table(name, schema=schema or None)


def _require_same_entity(measure: Measure, dimension: Dimension) -> None:
    if dimension.entity != measure.entity:
        raise CrossEntityError(measure, dimension)
