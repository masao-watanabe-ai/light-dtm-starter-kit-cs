from pydantic import BaseModel, Field
from typing import Literal

# Semantics of route / action combinations:
#
#   route="auto",  action="reply"       → automated reply sent, no human involved
#   route="auto",  action="escalate"    → automatically forwarded to an upstream queue or
#                                         higher-priority processing system; NOT a human agent
#   route="human", action="assign_queue"→ placed in a human review queue
#   route="hold",  action="none"        → no action taken; awaiting further context


class Decision(BaseModel):
    inquiry_id: str
    route: Literal["auto", "human", "hold"] = Field(
        default="hold",
        description=(
            "Routing target. "
            "'auto' = handled by an automated system (escalation is upstream queue, not human); "
            "'human' = human agent review required; "
            "'hold' = no action yet."
        ),
    )
    action: Literal["reply", "assign_queue", "escalate", "none"] = Field(
        default="none",
        description=(
            "Concrete action to execute. "
            "'reply' = send automated reply; "
            "'assign_queue' = place in human review queue; "
            "'escalate' = forward to upstream high-priority queue (automated, not human); "
            "'none' = take no action."
        ),
    )
    decision_state: Literal["completed", "requires_human", "waiting"] = "waiting"
    applied_rule: str = Field(
        default="",
        description="Identifier (name) of the decision rule that was matched.",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of why this rule was applied.",
    )
    confidence: float = 0.0
    risk_flags: list[str] = []
