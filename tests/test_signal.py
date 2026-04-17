import pytest
from app.models.inquiry import Inquiry
from app.services.signal_service import SignalService


def _make_svc() -> SignalService:
    svc = SignalService.__new__(SignalService)
    svc._llm_active = False
    from app.llm.client import LLMClient
    svc._client = LLMClient()
    return svc


def _inquiry(text: str, priority: int = 0, category: str = None,
             urgency: float = None, confidence: float = None,
             risk_flags: list = None) -> Inquiry:
    return Inquiry(
        id="test-inq",
        text=text,
        priority=priority,
        category=category,
        urgency=urgency,
        confidence=confidence,
        risk_flags=risk_flags or [],
    )


class TestUrgency:
    def test_keyword_boosts_urgency(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("緊急対応が必要です", priority=3))
        assert sig.urgency >= 0.6

    def test_priority_contributes(self):
        svc = _make_svc()
        low = svc.to_signal(_inquiry("お問い合わせです", priority=0))
        high = svc.to_signal(_inquiry("お問い合わせです", priority=7))
        assert high.urgency > low.urgency

    def test_explicit_urgency_overrides(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("urgent critical crisis", priority=10, urgency=0.1))
        assert sig.urgency == pytest.approx(0.1, abs=0.001)

    def test_urgency_clamped_to_one(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("urgent critical error", priority=10))
        assert sig.urgency <= 1.0


class TestConfidence:
    def test_long_text_raises_confidence(self):
        svc = _make_svc()
        short = svc.to_signal(_inquiry("hi"))
        long = svc.to_signal(_inquiry("Please help me with my account billing issue today."))
        assert long.confidence > short.confidence

    def test_category_raises_confidence(self):
        svc = _make_svc()
        without = svc.to_signal(_inquiry("Please help me"))
        with_cat = svc.to_signal(_inquiry("Please help me", category="billing"))
        assert with_cat.confidence > without.confidence

    def test_explicit_confidence_overrides(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("Please help me with billing and account", confidence=0.2))
        assert sig.confidence == pytest.approx(0.2, abs=0.001)


class TestRiskFlags:
    def test_complaint_keyword_detected(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("クレームを入れたい。返金を求めます"))
        assert "complaint" in sig.risk_flags

    def test_legal_keyword_detected(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("This is a legal matter involving a lawsuit."))
        assert "legal" in sig.risk_flags

    def test_system_error_keyword_detected(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("System is down, error occurred."))
        assert "system_error" in sig.risk_flags

    def test_explicit_flags_merged(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("Normal inquiry", risk_flags=["pii"]))
        assert "pii" in sig.risk_flags

    def test_multiple_flags_detected(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("緊急：セキュリティ侵害が発生、法的対応を検討中"))
        assert len(sig.risk_flags) >= 2

    def test_risk_flags_sorted(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("legal lawsuit complaint"))
        assert sig.risk_flags == sorted(sig.risk_flags)


class TestSignalMetadata:
    def test_extraction_mode_is_fallback(self):
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("test"))
        assert sig.metadata["extraction_mode"] == "fallback"

    def test_signal_id_is_uuid(self):
        import uuid
        svc = _make_svc()
        sig = svc.to_signal(_inquiry("test"))
        uuid.UUID(sig.id)  # raises if invalid
