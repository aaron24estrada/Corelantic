"""Resolve join paths across the entity graph.

Entities declare key edges (``Entity.joins``); together they form an undirected graph.
``find_join_path`` returns the shortest sequence of directed steps from a base entity to
a target — the joins the compiler must apply so a metric on one table can be grouped by a
dimension on another. Pure registry logic (no SQLAlchemy), so it stays on the semantic
side of the one-way ``query → semantic`` dependency.
"""

from collections import deque
from dataclasses import dataclass

from app.semantic.errors import NoJoinPathError
from app.semantic.models import SemanticRegistry


@dataclass(frozen=True)
class JoinStep:
    """One hop: join ``to_entity`` on ``from_entity.from_column == to_entity.to_column``."""

    from_entity: str
    from_column: str
    to_entity: str
    to_column: str


def _adjacency(registry: SemanticRegistry) -> dict[str, list[JoinStep]]:
    graph: dict[str, list[JoinStep]] = {}
    for entity in registry.entities.values():
        for edge in entity.joins:
            # An edge is traversable in both directions.
            graph.setdefault(entity.name, []).append(
                JoinStep(entity.name, edge.left, edge.to, edge.right)
            )
            graph.setdefault(edge.to, []).append(
                JoinStep(edge.to, edge.right, entity.name, edge.left)
            )
    return graph


def find_join_path(base: str, target: str, registry: SemanticRegistry) -> list[JoinStep]:
    """The shortest path of join steps from ``base`` to ``target`` (empty if equal)."""

    if base == target:
        return []

    graph = _adjacency(registry)
    came_from: dict[str, JoinStep] = {}
    seen = {base}
    queue = deque([base])
    while queue:
        current = queue.popleft()
        for step in graph.get(current, []):
            if step.to_entity in seen:
                continue
            seen.add(step.to_entity)
            came_from[step.to_entity] = step
            if step.to_entity == target:
                queue.clear()
                break
            queue.append(step.to_entity)

    if target not in came_from:
        raise NoJoinPathError(base, target)

    path: list[JoinStep] = []
    node = target
    while node != base:
        step = came_from[node]
        path.append(step)
        node = step.from_entity
    path.reverse()
    return path
