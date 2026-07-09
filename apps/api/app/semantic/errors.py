"""Errors raised when the semantic registry cannot resolve or define its vocabulary.

Metric and dimension lookups fail when an *intent* names vocabulary we do not define —
a client error that maps to a 404 at the HTTP boundary, never a guess. Entity and
measure lookups back the internal references between the types, and a metric whose
component measures span entities is a definition error; both are caught at load by
``validate_registry`` (authoring errors, not request errors).
"""


class SemanticError(Exception):
    """Base for semantic-layer lookup and definition failures."""


class UnknownEntityError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown entity: {name!r}.")
        self.name = name


class UnknownMeasureError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown measure: {name!r}.")
        self.name = name


class UnknownMetricError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown metric: {name!r}.")
        self.name = name


class UnknownConstantError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown constant: {name!r}.")
        self.name = name


class InvalidFormulaError(SemanticError):
    """A derived metric's formula is not a supported expression.

    Formulas are a tiny language — component-measure names, numeric literals, and the
    binary operators ``+ - * /`` (plus unary minus). Anything else, or a name that is not
    one of the metric's declared measures, is a definition error caught at load.
    """

    def __init__(self, expression: str, reason: str) -> None:
        super().__init__(f"Invalid formula {expression!r}: {reason}.")
        self.expression = expression
        self.reason = reason


class MixedEntityError(SemanticError):
    """A metric's component measures live on more than one entity.

    Ratio and derived metrics compose measures; a metric aggregates one fact entity.
    Combining measures from different entities is not something a single metric expresses
    (join dimensions in, rather than measures across facts).
    """

    def __init__(self, metric: str, entities: list[str]) -> None:
        super().__init__(
            f"Metric {metric!r} combines measures across entities {entities}; "
            f"a metric aggregates a single entity."
        )
        self.metric = metric
        self.entities = entities


class DuplicateNameError(SemanticError):
    """The same name is defined twice — across files, or as a repeated YAML key.

    Names are identifiers; a silent last-writer-wins merge (or pyyaml keeping the last of
    two duplicate keys) would hide one definition. A duplicate is an authoring mistake we
    surface at load rather than silently drop.
    """

    def __init__(self, kind: str, name: str) -> None:
        super().__init__(f"Duplicate {kind} {name!r}.")
        self.kind = kind
        self.name = name


class MalformedRegistryError(SemanticError):
    """A registry file is not the expected shape (a mapping of collections of definitions)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Malformed registry: {reason}.")
        self.reason = reason


class DisallowedSourceError(SemanticError):
    """An entity's source names a schema outside the configured allow-list."""

    def __init__(self, entity: str, source: str, allowed: list[str]) -> None:
        super().__init__(f"Entity {entity!r} source {source!r} not in allowed schemas {allowed}.")
        self.entity = entity
        self.source = source


class AmbiguousTermError(SemanticError):
    """A name or synonym would match more than one metric (or dimension).

    Synonyms exist so the agent can map natural language to one definition; a term that
    resolves to two is not usable for matching and is rejected at load.
    """

    def __init__(self, kind: str, term: str, names: list[str]) -> None:
        super().__init__(f"Term {term!r} matches more than one {kind}: {names}.")
        self.kind = kind
        self.term = term
        self.names = names


class NoJoinPathError(SemanticError):
    """No sequence of declared join edges connects two entities.

    A dimension on a different entity than the metric's is reached by joining along the
    entities' declared key edges. When the graph has no path between them, the query
    cannot be expressed — the entities are simply not related in the model.
    """

    def __init__(self, base: str, target: str) -> None:
        super().__init__(f"No join path from entity {base!r} to {target!r}.")
        self.base = base
        self.target = target


class JoinFanOutError(SemanticError):
    """A required join is one-to-many and would inflate the fact's measures.

    The compiler joins before aggregating, so joining a table with many rows per fact row
    multiplies the fact rows — inflating count(*), sum(...), and every metric built on
    them. Until cardinality-aware aggregation lands, such a join is rejected rather than
    silently returning wrong numbers.
    """

    def __init__(self, from_entity: str, to_entity: str) -> None:
        super().__init__(
            f"Joining {to_entity!r} onto {from_entity!r} is one-to-many; it would inflate "
            f"the fact's measures. Check the edge cardinality if that is unexpected, group "
            f"by a different dimension, or add fan-out-safe aggregation."
        )
        self.from_entity = from_entity
        self.to_entity = to_entity


class DuplicateJoinError(SemanticError):
    """An entity declares more than one join edge to the same target.

    Without named join roles, two edges to the same entity are contradictory — the join
    path taken would depend on declaration order. Surface it at load.
    """

    def __init__(self, entity: str, target: str) -> None:
        super().__init__(f"Entity {entity!r} declares more than one join edge to {target!r}.")
        self.entity = entity
        self.target = target


class UnknownDimensionError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown dimension: {name!r}.")
        self.name = name
