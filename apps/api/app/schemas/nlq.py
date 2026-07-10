from pydantic import BaseModel, Field

from app.schemas.query import ResultSet


class AskRequest(BaseModel):
    question: str = Field(description="The user's natural-language question about the data.")


class AskResponse(BaseModel):
    question: str = Field(description="The question that was asked.")
    result: ResultSet = Field(
        description="Rows, their column schema, and the intent the model actually ran."
    )
    narrative: str = Field(description="Short narrative grounded strictly in the rows.")
    # The chart payload is intentionally absent until the chart-spec format is decided
    # (docs O-5); it attaches here once the frontend contract is fixed.
