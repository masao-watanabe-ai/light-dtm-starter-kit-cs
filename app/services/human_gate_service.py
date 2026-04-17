from app.models.decision import Decision


class HumanGateService:
    """Determines whether a Decision requires human review."""

    def requires_human(self, decision: Decision) -> bool:
        return decision.action == "human" or decision.confidence < 0.5
