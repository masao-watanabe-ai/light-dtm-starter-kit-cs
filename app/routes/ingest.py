from fastapi import APIRouter
from app.models.inquiry import Inquiry
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingest", tags=["ingest"])
_service = IngestionService()


@router.post("/", response_model=Inquiry)
def ingest(payload: dict) -> Inquiry:
    return _service.ingest(payload)
