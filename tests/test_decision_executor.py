from app.models.signal import Signal
from app.models.decision import Decision
from integrations.decision_executor.local_executor import LocalExecutor


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        id="sig-001",
        source="api",
        content="test inquiry",
        urgency=0.5,
        confidence=0.7,
        risk_flags=[],
    )
    defaults.update(kwargs)
    return Signal(**defaults)


def _make_context(inquiry_id: str = "inq-001", matched_rule: dict = None) -> dict:
    rule = matched_rule or {
        "name": "default_auto_reply",
        "reason": "No high-risk flags detected.",
        "route": "auto",
        "action": "reply",
        "decision_state": "completed",
        "confidence": 0.70,
    }
    return {"inquiry_id": inquiry_id, "matched_rule": rule}


class TestLocalExecutor:
    def test_returns_decision(self):
        result = LocalExecutor().execute(_make_signal(), _make_context())
        assert isinstance(result, Decision)

    def test_route_from_rule(self):
        ctx = _make_context(matched_rule={
            "name": "complaint_or_legal_human",
            "reason": "Human required.",
            "route": "human",
            "action": "assign_queue",
            "decision_state": "requires_human",
            "confidence": 0.80,
        })
        result = LocalExecutor().execute(_make_signal(), ctx)
        assert result.route == "human"
        assert result.action == "assign_queue"
        assert result.decision_state == "requires_human"

    def test_applied_rule_set(self):
        result = LocalExecutor().execute(_make_signal(), _make_context())
        assert result.applied_rule == "default_auto_reply"

    def test_reason_propagated(self):
        result = LocalExecutor().execute(_make_signal(), _make_context())
        assert "No high-risk flags" in result.reason

    def test_risk_flags_from_signal(self):
        sig = _make_signal(risk_flags=["complaint", "legal"])
        result = LocalExecutor().execute(sig, _make_context())
        assert result.risk_flags == ["complaint", "legal"]

    def test_confidence_from_rule(self):
        result = LocalExecutor().execute(_make_signal(), _make_context())
        assert result.confidence == 0.70

    def test_inquiry_id_set(self):
        result = LocalExecutor().execute(_make_signal(), _make_context(inquiry_id="inq-xyz"))
        assert result.inquiry_id == "inq-xyz"

    def test_fallback_defaults_when_no_matched_rule(self):
        ctx = {"inquiry_id": "inq-001"}
        result = LocalExecutor().execute(_make_signal(), ctx)
        assert result.route == "hold"
        assert result.action == "none"
        assert result.decision_state == "waiting"

    def test_executor_mode(self):
        assert LocalExecutor.executor_mode == "local"


class TestRuleVariants:
    def test_critical_risk_escalate(self):
        ctx = _make_context(matched_rule={
            "name": "critical_risk_escalate",
            "reason": "High-risk flags detected.",
            "route": "auto",
            "action": "escalate",
            "decision_state": "completed",
            "confidence": 0.95,
        })
        sig = _make_signal(risk_flags=["critical"])
        result = LocalExecutor().execute(sig, ctx)
        assert result.route == "auto"
        assert result.action == "escalate"
        assert result.confidence == 0.95

    def test_low_confidence_hold(self):
        ctx = _make_context(matched_rule={
            "name": "low_confidence_hold",
            "reason": "Signal confidence below threshold.",
            "route": "hold",
            "action": "none",
            "decision_state": "waiting",
            "confidence": 0.55,
        })
        sig = _make_signal(confidence=0.2)
        result = LocalExecutor().execute(sig, ctx)
        assert result.route == "hold"
        assert result.decision_state == "waiting"
