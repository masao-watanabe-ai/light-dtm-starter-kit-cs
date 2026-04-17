import json
from datetime import datetime
from pathlib import Path
from app.models.trace import Trace
from integrations.trace_store.base import BaseTraceStore


class FileTraceStore(BaseTraceStore):
    """Persists traces as newline-delimited JSON in a local file.
    Also exports full pipeline snapshots as individual JSON files."""

    store_mode: str = "file"

    def __init__(self, path: str = "traces/traces.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._exports_dir = self._path.parent / "exports"
        self._exports_dir.mkdir(parents=True, exist_ok=True)

    def save(self, trace: Trace) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(trace.model_dump_json() + "\n")

    def list_all(self) -> list[Trace]:
        if not self._path.exists():
            return []
        traces = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(Trace.model_validate_json(line))
        return traces

    def save_export(self, inquiry_id: str, data: dict) -> Path:
        """Write a full pipeline snapshot as a single JSON file under traces/exports/."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = self._exports_dir / f"{inquiry_id}_{ts}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return file_path
