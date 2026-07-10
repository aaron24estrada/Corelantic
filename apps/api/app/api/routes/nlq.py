from datetime import date

from fastapi import APIRouter

from app.api.dependencies import OrchestratorDep
from app.schemas.nlq import AskRequest, AskResponse

router = APIRouter(prefix="/nlq", tags=["nlq"])


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, orchestrator: OrchestratorDep) -> AskResponse:
    answer = await orchestrator.ask(request.question, today=date.today())
    return AskResponse(
        question=request.question,
        result=answer.result,
        narrative=answer.narrative,
    )
