from fastapi import APIRouter

from app.api.dependencies import OrchestratorDep
from app.schemas.nlq import AskRequest, AskResponse

router = APIRouter(prefix="/nlq", tags=["nlq"])


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, orchestrator: OrchestratorDep) -> AskResponse:
    result = await orchestrator.ask(request.question)
    return AskResponse(
        question=request.question,
        intent=result.intent,
        rows=result.rows,
        narrative=result.narrative,
    )
