from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class Trace(BaseModel):
    trace_id: str
    inquiry_id: str
    step: str
    trace_version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    applied_rule: str = ""   # identifier of the matched rule (e.g. "critical_risk_escalate")
    reason: str = ""         # human-readable explanation of why the rule was applied
    decision_path: list[str] = []
    executor_mode: str = "local"   # "local" | "orchestrator"
    trace_store_mode: str = "file" # "file" | "ledger"
    payload: Optional[Any] = None
    created_at: Optional[datetime] = None  # deprecated, kept for backward compat
