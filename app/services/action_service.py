from app.models.decision import Decision


class ActionService:
    """Executes or delegates actions based on a Decision."""

    def execute(self, decision: Decision) -> dict:
        return {
            "inquiry_id": decision.inquiry_id,
            "action": decision.action,
            "status": "pending",
        }
