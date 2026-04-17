from app.models.signal import Signal
from app.models.decision import Decision
from integrations.decision_executor.base import BaseDecisionExecutor


class LocalExecutor(BaseDecisionExecutor):
    """Executes decisions in-process — no external system required."""

    executor_mode: str = "local"

    def execute(self, signal: Signal, context: dict) -> Decision:
        matched = context.get("matched_rule", {})
        return Decision(
            inquiry_id=context["inquiry_id"],
            route=matched.get("route", "hold"),
            action=matched.get("action", "none"),
            decision_state=matched.get("decision_state", "waiting"),
            applied_rule=matched.get("name", "unknown"),
            reason=matched.get("reason", ""),
            confidence=float(matched.get("confidence", signal.confidence)),
            risk_flags=signal.risk_flags,
        )
