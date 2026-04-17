from app.models.decision import Decision
from app.models.trace import Trace
from app.services.view_model_service import ViewModelService


def _make_decision(inquiry_id: str = "inq-001") -> Decision:
    return Decision(
        inquiry_id=inquiry_id,
        route="auto",
        action="reply",
        decision_state="completed",
        applied_rule="default_auto_reply",
        reason="No high-risk flags.",
        confidence=0.70,
        risk_flags=[],
    )


def _make_trace(trace_id: str = "t-001") -> Trace:
    return Trace(
        trace_id=trace_id,
        inquiry_id="inq-001",
        step="decision_run",
        applied_rule="default_auto_reply",
        reason="No high-risk flags.",
        decision_path=["preprocess", "signal_extract", "rule_match:default_auto_reply", "execute"],
        executor_mode="local",
        trace_store_mode="file",
    )


class TestViewModelService:
    def test_returns_dict(self):
        svc = ViewModelService()
        result = svc.build_demo_context([], [])
        assert isinstance(result, dict)

    def test_total_counts(self):
        svc = ViewModelService()
        decisions = [_make_decision("inq-001"), _make_decision("inq-002")]
        traces = [_make_trace("t-001")]
        result = svc.build_demo_context(decisions, traces)
        assert result["total_decisions"] == 2
        assert result["total_traces"] == 1

    def test_empty_inputs(self):
        svc = ViewModelService()
        result = svc.build_demo_context([], [])
        assert result["total_decisions"] == 0
        assert result["total_traces"] == 0
        assert result["decisions"] == []

    def test_decisions_serialized_as_dicts(self):
        svc = ViewModelService()
        result = svc.build_demo_context([_make_decision()], [])
        assert isinstance(result["decisions"][0], dict)
        assert result["decisions"][0]["route"] == "auto"

    def test_decisions_list_length_matches(self):
        svc = ViewModelService()
        decisions = [_make_decision(f"inq-{i:03d}") for i in range(5)]
        result = svc.build_demo_context(decisions, [])
        assert len(result["decisions"]) == 5
