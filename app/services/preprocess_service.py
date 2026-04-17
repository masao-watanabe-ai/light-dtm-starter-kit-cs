from app.models.inquiry import Inquiry


class PreprocessService:
    """Normalises and enriches an Inquiry before decision-making."""

    def preprocess(self, inquiry: Inquiry) -> Inquiry:
        inquiry.text = inquiry.text.strip()
        return inquiry
