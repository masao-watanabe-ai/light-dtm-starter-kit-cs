from fastapi import APIRouter
from app.models.decision import Decision

router = APIRouter(prefix="/decision", tags=["decision"])


@router.get("/", response_model=list[Decision])
def list_decisions() -> list[Decision]:
    # Placeholder — LLM / rule engine not yet connected
    return []
