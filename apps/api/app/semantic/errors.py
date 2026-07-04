"""Errors raised when a name cannot be resolved in the semantic registry.

Metric and dimension lookups fail when an *intent* names vocabulary we do not define —
a client error that maps to a 404 at the HTTP boundary, never a guess. Entity and
measure lookups back the internal references between the four types; a dangling one is
caught at load by ``validate_registry`` (an authoring error, not a request error).
"""


class SemanticError(Exception):
    """Base for semantic-layer lookup failures."""


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


class UnknownDimensionError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown dimension: {name!r}.")
        self.name = name
