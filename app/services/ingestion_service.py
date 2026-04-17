from app.models.inquiry import Inquiry


class IngestionService:
    """Receives raw input and converts it to an Inquiry."""

    def ingest(self, raw: dict) -> Inquiry:
        return Inquiry(
            id=raw.get("id", ""),
            text=raw.get("text", ""),
            category=raw.get("category"),
            priority=raw.get("priority", 0),
        )
