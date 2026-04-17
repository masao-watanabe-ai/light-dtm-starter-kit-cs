import logging
import uuid
from datetime import datetime

from app.config import settings
from app.models.decision import Decision
from app.models.decision_result import DecisionResult
from app.models.inquiry import Inquiry
from app.models.signal import Signal
from app.models.trace import Trace
from app.services.preprocess_service import PreprocessService
from app.services.rule_loader import RuleLoader
from app.services.signal_service import SignalService
from integrations.decision_executor.local_executor import LocalExecutor
from integrations.decision_executor.orchestrator_adapter import OrchestratorAdapter
from integrations.trace_store.file_store import FileTraceStore
from integrations.trace_store.ledger_adapter import LedgerAdapter

logger = logging.getLogger(__name__)

_TRACE_VERSION = "1.0"


class DecisionPipelineService:
    """
    Orchestrates the decision pipeline:
      Inquiry → preprocess → signal_extract → rule_match
              → execute(signal, context) → trace → DecisionResult

    Executor selection (at startup, from settings.decision_mode):
      "local"        → LocalExecutor (in-process, always succeeds)
      "orchestrator" → OrchestratorAdapter (HTTP); falls back to local on error
    """

    def __init__(self) -> None:
        self._preprocess = PreprocessService()
        self._signal_svc = SignalService()
        self._rule_loader = RuleLoader()
        if settings.decision_mode == "orchestrator":
            self._executor = OrchestratorAdapter()
            logger.info(
                "DecisionPipeline: using OrchestratorAdapter (endpoint=%s)",
                settings.orchestrator_endpoint or "<not set>",
            )
        else:
            self._executor = LocalExecutor()
            logger.info("DecisionPipeline: using LocalExecutor.")
        if settings.trace_mode == "ledger":
            self._store = LedgerAdapter()
            logger.info(
                "DecisionPipeline: using LedgerAdapter (endpoint=%s)",
                settings.ledger_endpoint or "<not set>",
            )
        else:
            self._store = FileTraceStore()
            logger.info("DecisionPipeline: using FileTraceStore.")

    def run(self, inquiry: Inquiry) -> DecisionResult:
        decision_path: list[str] = []

        # 1. Preprocess
        inquiry = self._preprocess.preprocess(inquiry)
        decision_path.append("preprocess")

        # 2. Signal extraction (urgency / confidence / risk_flags)
        signal: Signal = self._signal_svc.to_signal(inquiry)
        decision_path.append("signal_extract")

        # 3. Rule matching (signal-centric, no priority dependency)
        rules = self._rule_loader.load().get("rules", [])
        matched = self._match_rule(signal, rules)
        decision_path.append(f"rule_match:{matched['name']}")

        # 4. Execute: signal + context → Decision
        context = {
            "inquiry_id": inquiry.id,
            "matched_rule": matched,
        }
        decision: Decision = self._executor.execute(signal, context)

        # Resolve executor_info written by OrchestratorAdapter (or absent for LocalExecutor)
        executor_info: dict = context.get("executor_info", {})
        if executor_info.get("fallback"):
            decision_path.append("execute:local_fallback")
        else:
            decision_path.append("execute")

        # Effective executor mode for trace (may differ from self._executor.executor_mode
        # when OrchestratorAdapter fell back to local)
        effective_executor_mode = executor_info.get("mode") or self._executor.executor_mode

        # 5. Build and persist Trace with full metadata
        trace_id = str(uuid.uuid4())
        now = datetime.utcnow()
        trace_payload: dict = {
            "signal_id": signal.id,
            "urgency": signal.urgency,
            "confidence": signal.confidence,
            "risk_flags": signal.risk_flags,
            "route": decision.route,
            "action": decision.action,
            "decision_state": decision.decision_state,
        }
        if executor_info:
            trace_payload["executor_info"] = executor_info

        trace = Trace(
            trace_id=trace_id,
            inquiry_id=inquiry.id,
            step="decision_run",
            trace_version=_TRACE_VERSION,
            timestamp=now,
            applied_rule=decision.applied_rule,
            reason=decision.reason,
            decision_path=decision_path,
            executor_mode=effective_executor_mode,
            trace_store_mode=self._store.store_mode,
            payload=trace_payload,
            created_at=now,
        )
        # save() may mutate trace.payload["trace_store_info"] (LedgerAdapter)
        self._store.save(trace)

        # 6. Export full pipeline snapshot to traces/exports/
        # Propagate trace_store_info (written by LedgerAdapter.save) into the
        # export JSON so both outputs reflect the actual store outcome.
        export_data: dict = {
            "inquiry": inquiry.model_dump(),
            "signal": signal.model_dump(),
            "decision": decision.model_dump(),
            "trace_id": trace_id,
            "executed_at": now.isoformat(),
        }
        if isinstance(trace.payload, dict):
            trace_store_info = trace.payload.get("trace_store_info")
            if trace_store_info:
                export_data["trace_store_info"] = trace_store_info

        self._store.save_export(inquiry.id, export_data)

        return DecisionResult(
            inquiry_id=inquiry.id,
            route=decision.route,
            action=decision.action,
            decision_state=decision.decision_state,
            applied_rule=decision.applied_rule,
            reason=decision.reason,
            confidence=decision.confidence,
            risk_flags=decision.risk_flags,
            signal_id=signal.id,
            trace_id=trace_id,
            executed_at=now,
        )

    # ------------------------------------------------------------------
    # Rule matching helpers
    # ------------------------------------------------------------------

    def _match_rule(self, signal: Signal, rules: list) -> dict:
        for rule in rules:
            if self._satisfies(signal, rule.get("condition", {})):
                return {
                    "name": rule["name"],
                    "reason": rule.get("reason", ""),
                    "route": rule["route"],
                    "action": rule["action"],
                    "decision_state": rule["decision_state"],
                    "confidence": float(rule.get("base_confidence", 0.5)),
                }
        return {
            "name": "default_fallback",
            "reason": "No rule matched; inquiry held by safety net fallback.",
            "route": "hold",
            "action": "none",
            "decision_state": "waiting",
            "confidence": 0.5,
        }

    def _satisfies(self, signal: Signal, cond: dict) -> bool:
        if not cond:
            return True  # empty condition → catch-all

        if "urgency_gte" in cond:
            if signal.urgency < cond["urgency_gte"]:
                return False

        if "confidence_gte" in cond:
            if signal.confidence < cond["confidence_gte"]:
                return False

        if "confidence_lt" in cond:
            if signal.confidence >= cond["confidence_lt"]:
                return False

        if "risk_flags_any" in cond:
            if not any(f in signal.risk_flags for f in cond["risk_flags_any"]):
                return False

        if "risk_flags_all" in cond:
            if not all(f in signal.risk_flags for f in cond["risk_flags_all"]):
                return False

        return True
