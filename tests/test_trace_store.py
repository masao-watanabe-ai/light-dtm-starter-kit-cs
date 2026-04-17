import json
from pathlib import Path
from datetime import datetime
from app.models.trace import Trace
from integrations.trace_store.file_store import FileTraceStore


def _make_trace(trace_id: str = "t-001", inquiry_id: str = "inq-001") -> Trace:
    return Trace(
        trace_id=trace_id,
        inquiry_id=inquiry_id,
        step="decision_run",
        applied_rule="default_auto_reply",
        reason="No high-risk flags.",
        decision_path=["preprocess", "signal_extract", "rule_match:default_auto_reply", "execute"],
        executor_mode="local",
        trace_store_mode="file",
        payload={"urgency": 0.5, "confidence": 0.7, "route": "auto"},
    )


class TestFileTraceStoreSave:
    def test_save_creates_jsonl_file(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace())
        assert (tmp_path / "traces.jsonl").exists()

    def test_save_appends_lines(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace("t-001"))
        store.save(_make_trace("t-002"))
        lines = (tmp_path / "traces.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_saved_line_is_valid_json(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace())
        line = (tmp_path / "traces.jsonl").read_text().strip()
        data = json.loads(line)
        assert data["trace_id"] == "t-001"


class TestFileTraceStoreListAll:
    def test_list_all_empty_when_no_file(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        assert store.list_all() == []

    def test_list_all_returns_saved_traces(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace("t-001"))
        store.save(_make_trace("t-002"))
        traces = store.list_all()
        assert len(traces) == 2
        ids = {t.trace_id for t in traces}
        assert ids == {"t-001", "t-002"}

    def test_list_all_returns_trace_objects(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace())
        result = store.list_all()
        assert all(isinstance(t, Trace) for t in result)

    def test_list_all_preserves_payload(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        store.save(_make_trace())
        t = store.list_all()[0]
        assert t.payload["route"] == "auto"


class TestFileTraceStoreSaveExport:
    def test_save_export_creates_json_file(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        data = {"inquiry": {"id": "inq-001"}, "route": "auto"}
        path = store.save_export("inq-001", data)
        assert path.exists()
        assert path.suffix == ".json"

    def test_save_export_filename_contains_inquiry_id(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        path = store.save_export("inq-abc", {"route": "auto"})
        assert "inq-abc" in path.name

    def test_save_export_content_is_valid_json(self, tmp_path):
        store = FileTraceStore(path=str(tmp_path / "traces.jsonl"))
        data = {"route": "human", "action": "assign_queue"}
        path = store.save_export("inq-001", data)
        loaded = json.loads(path.read_text())
        assert loaded["route"] == "human"
