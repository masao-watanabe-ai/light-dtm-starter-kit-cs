from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Signal(BaseModel):
    id: str
    source: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_flags: list[str] = []
    metadata: Optional[dict] = None
