from pydantic import BaseModel, Field
from typing import Optional


class Inquiry(BaseModel):
    id: str
    text: str
    category: Optional[str] = None
    # priority is kept for backward compatibility; contributes to urgency computation
    priority: int = Field(default=0, ge=0, le=10)
    # explicit overrides — if provided, SignalService uses these directly
    urgency: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    risk_flags: list[str] = []
