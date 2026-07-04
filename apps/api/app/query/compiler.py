"""Compile a validated query intent into parameterized SQL.

This is the SQL trust boundary. Identifiers — the measure's aggregate expression, the
entity's source, and dimension columns — come only from the registry, which we author.
The caller's untrusted contribution is dimension *names* (validated against the registry,
so an unknown name raises rather than reaching SQL) and filter *values* (never
interpolated, always bound as parameters). Nothing the model or user provides is
concatenated into the statement, so there is no injection surface.

A metric resolves to its measure, and the measure to its entity: the entity supplies the
FROM, the measure the aggregate, the metric only the output name. The MVP scope is
aggregate + group-by + equality filters on a single entity. Time-grain bucketing and
cross-entity joins arrive with the real schema (docs O-2).
"""

from dataclasses import dataclass

from app.query.errors import CrossEntityError
from app.query.intent import QueryIntent
from app.semantic.models import Dimension, Measure, SemanticRegistry


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: dict[str, str]


def compile_query(intent: QueryIntent, registry: SemanticRegistry) -> CompiledQuery:
    metric = registry.metric(intent.metric)
    measure = registry.measure(metric.measure)
    entity = registry.entity(measure.entity)

    group_dimensions = [registry.dimension(name) for name in intent.group_by]
    for dimension in group_dimensions:
        _require_same_entity(measure, dimension)

    select_terms = [f"{dimension.column} AS {dimension.name}" for dimension in group_dimensions]
    select_terms.append(f"{measure.expression} AS {metric.name}")

    params: dict[str, str] = {}
    conditions: list[str] = []
    for index, (name, value) in enumerate(intent.filters.items()):
        dimension = registry.dimension(name)
        _require_same_entity(measure, dimension)
        placeholder = f"f{index}"
        conditions.append(f"{dimension.column} = :{placeholder}")
        params[placeholder] = value

    sql = f"SELECT {', '.join(select_terms)} FROM {entity.source}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if group_dimensions:
        sql += " GROUP BY " + ", ".join(dimension.column for dimension in group_dimensions)

    return CompiledQuery(sql=sql, params=params)


def _require_same_entity(measure: Measure, dimension: Dimension) -> None:
    if dimension.entity != measure.entity:
        raise CrossEntityError(measure, dimension)
