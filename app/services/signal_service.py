import logging
import uuid
from datetime import datetime

from app.config import settings
from app.llm.client import LLMClient
from app.llm.parser import parse_response
from app.llm.prompt_builder import build_prompt
from app.models.inquiry import Inquiry
from app.models.signal import Signal

logger = logging.getLogger(__name__)

# ── Fallback: urgency keyword list ────────────────────────────────────────────
_URGENT_KEYWORDS = [
    "緊急", "urgent", "critical", "障害", "エラー",
    "error", "故障", "停止", "crisis",
]

# ── Fallback: risk flag keyword map ──────────────────────────────────────────
_RISK_FLAG_MAP: dict[str, list[str]] = {
    "complaint":    ["クレーム", "complaint", "不満", "返金", "苦情"],
    "legal":        ["法律", "訴訟", "legal", "lawsuit", "弁護士", "contract"],
    "system_error": ["障害", "エラー", "error", "故障", "停止", "exception", "system down"],
    "critical":     ["緊急", "urgent", "critical", "crisis", "immediately"],
    "security":     ["不正", "hack", "security", "breach", "unauthorized", "セキュリティ"],
    "pii":          ["個人情報", "マイナンバー", "住所", "電話番号", "personal information"],
}


class SignalService:
    """
    Converts an Inquiry into a Signal.

    Extraction strategy (priority order):
      1. LLM-based  — calls OpenAI-compatible API when llm_enabled=True and
                       OPENAI_API_KEY is set.
      2. Fallback   — keyword heuristics; always used when LLM is disabled or
                       when the LLM call fails for any reason (timeout, API
                       error, parse error, …).

    Explicit fields on the Inquiry (urgency, confidence, risk_flags) always
    override whatever the LLM or fallback returns.
    """

    def __init__(self) -> None:
        self._client = LLMClient()
        self._llm_active = settings.llm_enabled and bool(settings.openai_api_key)
        if self._llm_active:
            logger.info(
                "SignalService: LLM extraction enabled (model=%s, base=%s)",
                settings.openai_model,
                settings.openai_api_base,
            )
        else:
            logger.info("SignalService: LLM extraction disabled — using fallback heuristics.")

    # ── Public ────────────────────────────────────────────────────────────────

    def to_signal(self, inquiry: Inquiry, source: str = "api") -> Signal:
        """Extract a Signal from an Inquiry.

        Tries LLM extraction first; falls back to heuristics on any exception.
        """
        if self._llm_active:
            try:
                return self._extract_via_llm(inquiry, source)
            except Exception as exc:
                logger.warning(
                    "LLM signal extraction failed (inquiry_id=%s): %s — using fallback.",
                    inquiry.id,
                    exc,
                )
        return self._extract_fallback(inquiry, source)

    # ── LLM path ─────────────────────────────────────────────────────────────

    def _extract_via_llm(self, inquiry: Inquiry, source: str) -> Signal:
        system_prompt, user_prompt = build_prompt(inquiry.text)
        raw = self._client.complete(system_prompt, user_prompt)
        parsed = parse_response(raw)

        # Explicit inquiry fields take precedence over LLM output
        urgency = (
            round(inquiry.urgency, 3)
            if inquiry.urgency is not None
            else parsed["urgency"]
        )
        confidence = (
            round(inquiry.confidence, 3)
            if inquiry.confidence is not None
            else parsed["confidence"]
        )
        risk_flags = sorted(set(inquiry.risk_flags) | set(parsed["risk_flags"]))

        return Signal(
            id=str(uuid.uuid4()),
            source=source,
            content=inquiry.text,
            timestamp=datetime.utcnow(),
            urgency=urgency,
            confidence=confidence,
            risk_flags=risk_flags,
            metadata={
                "inquiry_priority":  inquiry.priority,
                "inquiry_category":  inquiry.category,
                "llm_category":      parsed["category"],
                "extraction_mode":   "llm",
                "llm_model":         settings.openai_model,
            },
        )

    # ── Fallback heuristics ───────────────────────────────────────────────────

    def _extract_fallback(self, inquiry: Inquiry, source: str) -> Signal:
        urgency = self._compute_urgency(inquiry)
        confidence = self._compute_confidence(inquiry)
        risk_flags = self._detect_risk_flags(inquiry)
        return Signal(
            id=str(uuid.uuid4()),
            source=source,
            content=inquiry.text,
            timestamp=datetime.utcnow(),
            urgency=urgency,
            confidence=confidence,
            risk_flags=risk_flags,
            metadata={
                "inquiry_priority": inquiry.priority,
                "inquiry_category": inquiry.category,
                "extraction_mode":  "fallback",
            },
        )

    def _compute_urgency(self, inquiry: Inquiry) -> float:
        """Return 0.0–1.0. Explicit value on Inquiry takes precedence."""
        if inquiry.urgency is not None:
            return round(inquiry.urgency, 3)
        base = min(inquiry.priority / 10.0, 0.7)
        if any(kw.lower() in inquiry.text.lower() for kw in _URGENT_KEYWORDS):
            base = min(base + 0.3, 1.0)
        return round(base, 3)

    def _compute_confidence(self, inquiry: Inquiry) -> float:
        """Return 0.0–1.0. Explicit value on Inquiry takes precedence."""
        if inquiry.confidence is not None:
            return round(inquiry.confidence, 3)
        score = 0.5
        text_len = len(inquiry.text.strip())
        if text_len >= 20:
            score += 0.2
        elif text_len < 5:
            score -= 0.2
        if inquiry.category:
            score += 0.1
        return round(max(0.0, min(1.0, score)), 3)

    def _detect_risk_flags(self, inquiry: Inquiry) -> list[str]:
        """Merge explicit Inquiry flags with keyword-detected flags."""
        flags: set[str] = set(inquiry.risk_flags)
        text_lower = inquiry.text.lower()
        for flag, keywords in _RISK_FLAG_MAP.items():
            if any(kw.lower() in text_lower for kw in keywords):
                flags.add(flag)
        return sorted(flags)
