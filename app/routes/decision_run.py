from fastapi import APIRouter, HTTPException
from app.models.inquiry import Inquiry
from app.models.decision_result import DecisionResult
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter(prefix="/api/decision", tags=["pipeline"])
_pipeline = DecisionPipelineService()


@router.post("/run", response_model=DecisionResult)
def run_decision(inquiry: Inquiry) -> DecisionResult:
    if not inquiry.id:
        raise HTTPException(status_code=422, detail="inquiry.id is required")
    if not inquiry.text.strip():
        raise HTTPException(status_code=422, detail="inquiry.text must not be empty")
    return _pipeline.run(inquiry)
