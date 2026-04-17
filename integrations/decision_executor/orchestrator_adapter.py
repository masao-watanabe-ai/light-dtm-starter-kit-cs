"""
OrchestratorAdapter — HTTP-based decision executor.

Calls an external orchestrator via HTTP POST.  On any failure (connection
error, timeout, non-2xx response, parse error, validation error) the adapter
transparently falls back to LocalExecutor and records the failure in
context["executor_info"].

Payload sent (POST application/json):
    {
      "inquiry_id": "<str>",
      "signal": {
          "id": "<str>",
          "urgency": 0.0–1.0,
          "confidence": 0.0–1.0,
          "risk_flags": ["..."],
          "content": "<str>"
      },
      "matched_rule": {
          "name": "<str>",
          "route": "auto"|"human"|"hold",
          "action": "reply"|"assign_queue"|"escalate"|"none",
          "decision_state": "completed"|"requires_human"|"waiting",
          "confidence": 0.0–1.0
      }
    }

Expected response (200 application/json):
    {
      "route": "auto"|"human"|"hold",
      "action": "reply"|"assign_queue"|"escalate"|"none",
      "decision_state": "completed"|"requires_human"|"waiting",
      "applied_rule": "<str>",          # optional
      "reason": "<str>",                # optional
      "confidence": 0.0–1.0,
      "queue": "<str>"                  # optional — target queue name
    }
"""

import logging

import httpx

from app.config import settings
from app.models.decision import Decision
from app.models.signal import Signal
from integrations.decision_executor.base import BaseDecisionExecutor
from integrations.decision_executor.local_executor import LocalExecutor

logger = logging.getLogger(__name__)

_VALID_ROUTES = frozenset({"auto", "human", "hold"})
_VALID_ACTIONS = frozenset({"reply", "assign_queue", "escalate", "none"})
_VALID_STATES = frozenset({"completed", "requires_human", "waiting"})


class OrchestratorAdapter(BaseDecisionExecutor):
    """
    Decision executor that delegates to an external HTTP orchestrator.

    Falls back to LocalExecutor when:
      - settings.orchestrator_endpoint is not configured
      - HTTP connection / timeout error
      - Non-2xx HTTP response
      - Response body is not valid JSON
      - Response is missing required fields or contains invalid Literal values
    """

    executor_mode: str = "orchestrator"

    def execute(self, signal: Signal, context: dict) -> Decision:
        """
        Try the external orchestrator; fall back to LocalExecutor on any error.

        Side effect: sets context["executor_info"] dict with:
            mode          — "orchestrator" | "local_fallback"
            fallback      — False | True
            fallback_reason — "" | reason string
            endpoint      — URL attempted (or "")
            queue         — queue name from orchestrator response (or "")
        """
        endpoint = settings.orchestrator_endpoint.strip()

        if not endpoint:
            logger.warning(
                "OrchestratorAdapter: orchestrator_endpoint is not set — falling back to local."
            )
            return self._fallback(signal, context, reason="endpoint_not_configured")

        payload = self._build_payload(signal, context)
        try:
            response = httpx.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=settings.orchestrator_timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning(
                "OrchestratorAdapter: request timed out (endpoint=%s): %s — falling back.",
                endpoint,
                exc,
            )
            return self._fallback(signal, context, reason=f"timeout: {exc}")
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OrchestratorAdapter: HTTP %s from %s — falling back.",
                exc.response.status_code,
                endpoint,
            )
            return self._fallback(
                signal, context, reason=f"http_error:{exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            logger.warning(
                "OrchestratorAdapter: connection error (endpoint=%s): %s — falling back.",
                endpoint,
                exc,
            )
            return self._fallback(signal, context, reason=f"connection_error: {exc}")

        try:
            data = response.json()
        except Exception as exc:
            logger.warning(
                "OrchestratorAdapter: failed to parse JSON response: %s — falling back.", exc
            )
            return self._fallback(signal, context, reason=f"json_parse_error: {exc}")

        try:
            decision = self._parse_response(data, signal, context)
        except ValueError as exc:
            logger.warning(
                "OrchestratorAdapter: invalid orchestrator response: %s — falling back.", exc
            )
            return self._fallback(signal, context, reason=f"validation_error: {exc}")

        # Success — record executor_info without fallback
        queue = str(data.get("queue", "")).strip()
        context["executor_info"] = {
            "mode": "orchestrator",
            "fallback": False,
            "fallback_reason": "",
            "endpoint": endpoint,
            "queue": queue,
        }
        logger.info(
            "OrchestratorAdapter: decision received (inquiry_id=%s, route=%s, queue=%s)",
            context.get("inquiry_id"),
            decision.route,
            queue or "<none>",
        )
        return decision

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_payload(self, signal: Signal, context: dict) -> dict:
        matched = context.get("matched_rule", {})
        return {
            "inquiry_id": context.get("inquiry_id", ""),
            "signal": {
                "id": signal.id,
                "urgency": signal.urgency,
                "confidence": signal.confidence,
                "risk_flags": signal.risk_flags,
                "content": signal.content,
            },
            "matched_rule": {
                "name": matched.get("name", ""),
                "route": matched.get("route", "hold"),
                "action": matched.get("action", "none"),
                "decision_state": matched.get("decision_state", "waiting"),
                "confidence": float(matched.get("confidence", 0.0)),
            },
        }

    def _parse_response(self, data: dict, signal: Signal, context: dict) -> Decision:
        """Validate and convert the orchestrator JSON response into a Decision."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

        route = str(data.get("route", "")).strip()
        if route not in _VALID_ROUTES:
            raise ValueError(f"Invalid route value: {route!r}")

        action = str(data.get("action", "")).strip()
        if action not in _VALID_ACTIONS:
            raise ValueError(f"Invalid action value: {action!r}")

        decision_state = str(data.get("decision_state", "")).strip()
        if decision_state not in _VALID_STATES:
            raise ValueError(f"Invalid decision_state value: {decision_state!r}")

        try:
            confidence = float(data.get("confidence", 0.0))
            confidence = round(max(0.0, min(1.0, confidence)), 3)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid confidence value: {data.get('confidence')!r}")

        return Decision(
            inquiry_id=context.get("inquiry_id", ""),
            route=route,
            action=action,
            decision_state=decision_state,
            applied_rule=str(data.get("applied_rule", "orchestrator")).strip(),
            reason=str(data.get("reason", "")).strip(),
            confidence=confidence,
            risk_flags=signal.risk_flags,
        )

    def _fallback(self, signal: Signal, context: dict, reason: str) -> Decision:
        """Execute LocalExecutor and record fallback info in context."""
        decision = LocalExecutor().execute(signal, context)
        context["executor_info"] = {
            "mode": "local_fallback",
            "fallback": True,
            "fallback_reason": reason,
            "endpoint": settings.orchestrator_endpoint.strip(),
            "queue": "",
        }
        return decision
