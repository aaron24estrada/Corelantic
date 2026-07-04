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

    Ratio and derived metrics compose measures; the MVP engine computes them over a
    single entity. Combining measures across entities needs join resolution (B3).
    """

    def __init__(self, metric: str, entities: list[str]) -> None:
        super().__init__(
            f"Metric {metric!r} combines measures across entities {entities}; "
            f"single-entity only (joins are B3)."
        )
        self.metric = metric
        self.entities = entities


class UnknownDimensionError(SemanticError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown dimension: {name!r}.")
        self.name = name
