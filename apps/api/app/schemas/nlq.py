from pydantic import BaseModel, Field

from app.schemas.chart import ChartSpec
from app.schemas.query import ResultSet


class AskRequest(BaseModel):
    question: str = Field(description="The user's natural-language question about the data.")


class AskResponse(BaseModel):
    question: str = Field(description="The question that was asked.")
    result: ResultSet = Field(
        description="Rows, their column schema, and the intent the model actually ran."
    )
    chart: ChartSpec | None = Field(
        default=None,
        description=(
            "The answer drawn, in the same shape the dashboard renders. Always null today: the "
            "orchestrator plans an intent but not yet a visual, so E3 populates it. The field is "
            "typed rather than absent so both surfaces share one contract and one <Chart>."
        ),
    )
    narrative: str = Field(description="Short narrative grounded strictly in the rows.")
