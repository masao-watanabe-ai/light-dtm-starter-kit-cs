"""
LedgerAdapter — HTTP-based trace store.

Streams each trace to an external ledger service via HTTP POST.  On any
failure (endpoint not configured, connection error, timeout, non-2xx response,
JSON parse error) the adapter transparently falls back to FileTraceStore and
records the failure inside trace.payload["trace_store_info"].

This mirrors the executor_info pattern from OrchestratorAdapter so that both
fallback sources are inspectable from the same trace object.

──────────────────────────────────────────────────────────────────────────────
Ledger API contract
──────────────────────────────────────────────────────────────────────────────

POST {ledger_endpoint}/traces
  Content-Type: application/json
  Body example:
    {
      "trace_id":      "550e8400-e29b-41d4-a716-446655440000",
      "inquiry_id":    "inq-001",
      "step":          "decision_run",
      "trace_version": "1.0",
      "timestamp":     "2026-04-17T05:00:00.000000",
      "applied_rule":  "critical_risk_escalate",
      "reason":        "High-risk flags detected …",
      "decision_path": ["preprocess", "signal_extract",
                        "rule_match:critical_risk_escalate", "execute"],
      "executor_mode": "local",
      "trace_store_mode": "ledger",
      "payload": {
        "signal_id":    "b6152fd1-…",
        "urgency":      0.85,
        "confidence":   0.72,
        "risk_flags":   ["critical", "system_error"],
        "route":        "auto",
        "action":       "escalate",
        "decision_state": "completed"
      },
      "created_at": "2026-04-17T05:00:00.000000"
    }

  Expected response (2xx, application/json):
    {
      "trace_id": "550e8400-…",   # ledger's own ID (may differ from request)
      "saved":    true
    }
    Any 2xx body is accepted; only the status code is used to confirm success.

GET {ledger_endpoint}/traces
  Expected response (2xx, application/json): array of trace objects
    [ { "trace_id": "…", … }, … ]

──────────────────────────────────────────────────────────────────────────────
trace_store_info written to trace.payload
──────────────────────────────────────────────────────────────────────────────

On success:
  "trace_store_info": {
    "mode":           "ledger",
    "fallback":       false,
    "fallback_reason": "",
    "endpoint":       "http://ledger.internal/api"
  }

On fallback:
  "trace_store_info": {
    "mode":           "file_fallback",
    "fallback":       true,
    "fallback_reason": "connection_error: [Errno 61] Connection refused",
    "endpoint":       "http://ledger.internal/api"
  }
"""

import logging

import httpx

from app.config import settings
from app.models.trace import Trace
from integrations.trace_store.base import BaseTraceStore
from integrations.trace_store.file_store import FileTraceStore

logger = logging.getLogger(__name__)


class LedgerAdapter(BaseTraceStore):
    """
    Trace store that delegates to an external HTTP ledger service.

    Falls back to FileTraceStore when:
      - settings.ledger_endpoint is not configured
      - HTTP connection / timeout error
      - Non-2xx HTTP response
      - Response body cannot be parsed (only logged; not fatal for save)

    Side effect of save():
      Writes a "trace_store_info" key into trace.payload (dict) so that both
      the JSONL log and the export JSON reflect the actual store outcome.
      The pipeline is responsible for propagating this into the export dict.

    save_export() always delegates to the internal FileTraceStore so a local
    backup is always written regardless of ledger availability.
    """

    store_mode: str = "ledger"

    def __init__(self) -> None:
        self._file_store = FileTraceStore(settings.trace_store_path)

    # ── Public interface ──────────────────────────────────────────────────────

    def save(self, trace: Trace) -> None:
        """
        Persist trace to ledger; fall back to local file on any error.

        Mutates trace.payload (must be a dict) to add "trace_store_info".
        """
        endpoint = settings.ledger_endpoint.strip()

        if not endpoint:
            logger.warning(
                "LedgerAdapter: ledger_endpoint is not set — falling back to file store."
            )
            self._fallback_save(trace, reason="endpoint_not_configured")
            return

        body = self._serialize(trace)
        try:
            response = httpx.post(
                f"{endpoint}/traces",
                json=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=settings.ledger_timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning(
                "LedgerAdapter: request timed out (endpoint=%s): %s — falling back.",
                endpoint,
                exc,
            )
            self._fallback_save(trace, reason=f"timeout: {exc}")
            return
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "LedgerAdapter: HTTP %s from %s — falling back.",
                exc.response.status_code,
                endpoint,
            )
            self._fallback_save(trace, reason=f"http_error:{exc.response.status_code}")
            return
        except httpx.RequestError as exc:
            logger.warning(
                "LedgerAdapter: connection error (endpoint=%s): %s — falling back.",
                endpoint,
                exc,
            )
            self._fallback_save(trace, reason=f"connection_error: {exc}")
            return

        # Success — annotate payload and log
        self._annotate(trace, mode="ledger", fallback=False, reason="", endpoint=endpoint)
        logger.info(
            "LedgerAdapter: trace saved (trace_id=%s, inquiry_id=%s)",
            trace.trace_id,
            trace.inquiry_id,
        )

    def save_export(self, inquiry_id: str, data: dict):
        """
        Always writes the export snapshot to the local file system.

        The caller (DecisionPipelineService) is responsible for adding
        trace_store_info to `data` before calling this method so that
        the export JSON also reflects the actual store outcome.
        """
        return self._file_store.save_export(inquiry_id, data)

    def list_all(self) -> list[Trace]:
        """
        Retrieve all traces from the ledger.
        Falls back to local FileTraceStore on any error.
        """
        endpoint = settings.ledger_endpoint.strip()
        if not endpoint:
            return self._file_store.list_all()

        try:
            response = httpx.get(
                f"{endpoint}/traces",
                headers={"Accept": "application/json"},
                timeout=settings.ledger_timeout,
            )
            response.raise_for_status()
            raw_list = response.json()
            if not isinstance(raw_list, list):
                raise ValueError(f"Expected list, got {type(raw_list).__name__}")
            return [Trace.model_validate(item) for item in raw_list]
        except Exception as exc:
            logger.warning(
                "LedgerAdapter: list_all failed (endpoint=%s): %s — using local file.",
                endpoint,
                exc,
            )
            return self._file_store.list_all()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _serialize(self, trace: Trace) -> dict:
        """Convert Trace to a plain dict for the HTTP body."""
        return trace.model_dump(mode="json")

    def _fallback_save(self, trace: Trace, reason: str) -> None:
        """Persist via FileTraceStore and annotate trace.payload accordingly."""
        endpoint = settings.ledger_endpoint.strip()
        self._annotate(trace, mode="file_fallback", fallback=True, reason=reason, endpoint=endpoint)
        self._file_store.save(trace)

    @staticmethod
    def _annotate(
        trace: Trace,
        *,
        mode: str,
        fallback: bool,
        reason: str,
        endpoint: str,
    ) -> None:
        """
        Write trace_store_info into trace.payload in-place.

        trace.payload is always a dict in this pipeline.  If it is somehow
        None or a non-dict type, the annotation is skipped with a warning.
        """
        if not isinstance(trace.payload, dict):
            logger.warning(
                "LedgerAdapter: trace.payload is not a dict (type=%s) — "
                "cannot annotate trace_store_info.",
                type(trace.payload).__name__,
            )
            return

        trace.payload["trace_store_info"] = {
            "mode": mode,
            "fallback": fallback,
            "fallback_reason": reason,
            "endpoint": endpoint,
        }
