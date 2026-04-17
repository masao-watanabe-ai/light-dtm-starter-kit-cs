from fastapi import APIRouter
from app.models.trace import Trace

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("/", response_model=list[Trace])
def list_traces() -> list[Trace]:
    # Placeholder — trace store not yet connected
    return []
