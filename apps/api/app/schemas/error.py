from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """The one error body every handler returns.

    ``code`` is stable and machine-readable; ``detail`` is for a human and may change.
    ``allowed`` is what makes a 422 actionable — the agent re-plans from it and the UI names
    the options — so it is present whenever the vocabulary that would have been accepted is
    computable.
    """

    detail: str = Field(description="Human-readable explanation. Never leaks internals.")
    code: str | None = Field(default=None, description="Stable machine-readable error code.")
    field: str | None = Field(default=None, description="The request field that was rejected.")
    allowed: list[str] | None = Field(
        default=None, description="Values that would have been accepted for that field."
    )
