"""Errors raised when an intent references vocabulary the registry does not define.

These map to 404s at the HTTP boundary — the caller named a metric or dimension we do
not know, which is a client error, never a guess.
"""


class SemanticError(Exception):
    """Base for semantic-layer lookup failures."""


class UnknownMetricError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown metric: {name!r}.")
        self.name = name


class UnknownDimensionError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown dimension: {name!r}.")
        self.name = name
