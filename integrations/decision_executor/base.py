from abc import ABC, abstractmethod
from app.models.signal import Signal
from app.models.decision import Decision


class BaseDecisionExecutor(ABC):
    """
    Abstract base for decision executors.

    Semantics of route / action pairs:
      route="auto",  action="reply"        → automated reply, no human involved
      route="auto",  action="escalate"     → automatically forwarded to an upstream queue
                                             or higher-priority processing system.
                                             NOTE: "auto + escalate" does NOT mean a human
                                             agent handles it — the forwarding itself is
                                             automated. Use route="human" when human review
                                             is required.
      route="human", action="assign_queue" → placed in a human review queue
      route="hold",  action="none"         → no action; awaiting additional context
    """

    executor_mode: str = "unknown"

    @abstractmethod
    def execute(self, signal: Signal, context: dict) -> Decision:
        """
        Args:
            signal:  Enriched Signal carrying urgency, confidence, and risk_flags.
            context: Dict containing at minimum:
                       - inquiry_id (str)
                       - matched_rule (dict with keys: name, reason, route, action,
                                       decision_state, confidence)
        Returns:
            Decision with applied_rule, reason, route, action, decision_state,
            confidence, and risk_flags fully populated.
        """
        ...
