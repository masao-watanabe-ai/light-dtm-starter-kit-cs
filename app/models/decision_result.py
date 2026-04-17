from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class DecisionResult(BaseModel):
    inquiry_id: str
    route: Literal["auto", "human", "hold"] = Field(
        description=(
            "Routing target. "
            "'auto' = automated system (escalate means upstream queue, not human); "
            "'human' = human review required; "
            "'hold' = awaiting further context."
        ),
    )
    action: Literal["reply", "assign_queue", "escalate", "none"] = Field(
        description=(
            "'reply' = automated reply sent; "
            "'assign_queue' = placed in human review queue; "
            "'escalate' = forwarded to upstream high-priority queue (automated); "
            "'none' = no action taken."
        ),
    )
    decision_state: Literal["completed", "requires_human", "waiting"]
    applied_rule: str = Field(
        description="Identifier (name) of the matched decision rule.",
    )
    reason: str = Field(
        description="Human-readable explanation of why this rule was applied.",
    )
    confidence: float
    risk_flags: list[str]
    signal_id: str
    trace_id: str
    executed_at: datetime
