"""Resolve join paths across the entity graph.

Entities declare key edges (``Entity.joins``); together they form an undirected graph.
``find_join_path`` returns the shortest sequence of directed steps from a base entity to
a target — the joins the compiler must apply so a metric on one table can be grouped by a
dimension on another. Pure registry logic (no SQLAlchemy), so it stays on the semantic
side of the one-way ``query → semantic`` dependency.
"""

from collections import deque
from dataclasses import dataclass, field

from app.semantic.errors import NoJoinPathError
from app.semantic.models import Cardinality, SemanticRegistry


@dataclass(frozen=True)
class JoinStep:
    """One hop: join ``to_entity`` on ``from_entity.from_column == to_entity.to_column``.

    ``fans_out`` is derived from the edge's cardinality — True when joining ``to_entity``
    yields many rows per ``from_entity`` row. It is metadata, not identity, so it is
    excluded from equality (a step is the same hop regardless).
    """

    from_entity: str
    from_column: str
    to_entity: str
    to_column: str
    fans_out: bool = field(default=False, compare=False)


def _adjacency(registry: SemanticRegistry) -> dict[str, list[JoinStep]]:
    graph: dict[str, list[JoinStep]] = {}
    for entity in registry.entities.values():
        for edge in entity.joins:
            # An edge is traversable both ways; a hop fans out when the direction lands on
            # the "many" side: forward for one_to_many, backward for many_to_one.
            forward_fans_out = edge.cardinality is Cardinality.ONE_TO_MANY
            backward_fans_out = edge.cardinality is Cardinality.MANY_TO_ONE
            graph.setdefault(entity.name, []).append(
                JoinStep(entity.name, edge.left, edge.to, edge.right, fans_out=forward_fans_out)
            )
            graph.setdefault(edge.to, []).append(
                JoinStep(edge.to, edge.right, entity.name, edge.left, fans_out=backward_fans_out)
            )
    return graph


def find_join_path(base: str, target: str, registry: SemanticRegistry) -> list[JoinStep]:
    """The shortest join path from ``base`` to ``target`` (empty if equal).

    A fan-out-free path is preferred: only when none exists does the search fall back to a
    path with a fan-out hop (which the compiler then rejects). This way a query is refused
    only when it truly cannot be answered without inflating the fact, not merely because
    the shortest path happens to fan out.
    """

    if base == target:
        return []

    graph = _adjacency(registry)
    path = _bfs(graph, base, target, safe_only=True)
    if path is None:
        path = _bfs(graph, base, target, safe_only=False)
    if path is None:
        raise NoJoinPathError(base, target)
    return path


def _bfs(
    graph: dict[str, list[JoinStep]], base: str, target: str, *, safe_only: bool
) -> list[JoinStep] | None:
    came_from: dict[str, JoinStep] = {}
    seen = {base}
    queue = deque([base])
    while queue:
        current = queue.popleft()
        for step in graph.get(current, []):
            if safe_only and step.fans_out:
                continue
            if step.to_entity in seen:
                continue
            seen.add(step.to_entity)
            came_from[step.to_entity] = step
            if step.to_entity == target:
                return _reconstruct(came_from, base, target)
            queue.append(step.to_entity)
    return None


def _reconstruct(came_from: dict[str, JoinStep], base: str, target: str) -> list[JoinStep]:
    path: list[JoinStep] = []
    node = target
    while node != base:
        step = came_from[node]
        path.append(step)
        node = step.from_entity
    path.reverse()
    return path
