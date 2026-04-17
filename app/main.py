from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routes import (
    ingest_router,
    decision_router,
    trace_router,
    demo_router,
    decision_run_router,
)

app = FastAPI(title="light-dtm-starter", version="0.1.0")

app.include_router(ingest_router)
app.include_router(decision_router)
app.include_router(trace_router)
app.include_router(demo_router)
app.include_router(decision_run_router)


@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
