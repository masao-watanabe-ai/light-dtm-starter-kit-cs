import json
from datetime import datetime
from app.models.trace import Trace


def _make_trace(**kwargs) -> Trace:
    defaults = dict(
        trace_id="trace-001",
        inquiry_id="inq-001",
        step="decision_run",
        applied_rule="default_auto_reply",
        reason="No high-risk flags.",
        decision_path=["preprocess", "signal_extract", "rule_match:default_auto_reply", "execute"],
        executor_mode="local",
        trace_store_mode="file",
        payload={"urgency": 0.5, "confidence": 0.7},
    )
    defaults.update(kwargs)
    return Trace(**defaults)


class TestTraceModel:
    def test_create_trace(self):
        t = _make_trace()
        assert t.trace_id == "trace-001"
        assert t.inquiry_id == "inq-001"
        assert t.step == "decision_run"

    def test_default_trace_version(self):
        t = _make_trace()
        assert t.trace_version == "1.0"

    def test_timestamp_set_automatically(self):
        t = _make_trace()
        assert isinstance(t.timestamp, datetime)

    def test_decision_path_preserved(self):
        path = ["preprocess", "signal_extract", "rule_match:low_confidence_hold", "execute"]
        t = _make_trace(decision_path=path)
        assert t.decision_path == path

    def test_payload_arbitrary_dict(self):
        payload = {"urgency": 0.9, "risk_flags": ["critical"], "route": "auto"}
        t = _make_trace(payload=payload)
        assert t.payload["route"] == "auto"


class TestTraceSerialization:
    def test_model_dump_json_roundtrip(self):
        t = _make_trace()
        raw = t.model_dump_json()
        restored = Trace.model_validate_json(raw)
        assert restored.trace_id == t.trace_id
        assert restored.applied_rule == t.applied_rule

    def test_json_contains_required_fields(self):
        t = _make_trace()
        data = json.loads(t.model_dump_json())
        for field in ("trace_id", "inquiry_id", "step", "applied_rule", "reason",
                      "decision_path", "executor_mode", "trace_store_mode"):
            assert field in data

    def test_empty_decision_path(self):
        t = _make_trace(decision_path=[])
        assert t.decision_path == []

    def test_none_payload(self):
        t = _make_trace(payload=None)
        assert t.payload is None
