from app.models.decision import Decision
from app.models.trace import Trace


class ViewModelService:
    """Builds view-friendly payloads for the demo UI."""

    def build_demo_context(self, decisions: list[Decision], traces: list[Trace]) -> dict:
        return {
            "total_decisions": len(decisions),
            "total_traces": len(traces),
            "decisions": [d.model_dump() for d in decisions],
        }
