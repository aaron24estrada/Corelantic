from pydantic import BaseModel, Field

from app.query.intent import QueryIntent


class AskRequest(BaseModel):
    question: str = Field(description="The user's natural-language question about the data.")


class AskResponse(BaseModel):
    question: str = Field(description="The question that was asked.")
    intent: QueryIntent = Field(description="The structured intent the model planned from it.")
    rows: list[dict[str, object]] = Field(description="Result rows the intent produced.")
    narrative: str = Field(description="Short narrative grounded strictly in the rows.")
    # The chart payload is intentionally absent until the chart-spec format is decided
    # (docs O-5); it attaches here once the frontend contract is fixed.
