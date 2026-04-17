from app.routes.ingest import router as ingest_router
from app.routes.decision import router as decision_router
from app.routes.trace import router as trace_router
from app.routes.demo_view import router as demo_router
from app.routes.decision_run import router as decision_run_router

__all__ = [
    "ingest_router",
    "decision_router",
    "trace_router",
    "demo_router",
    "decision_run_router",
]
