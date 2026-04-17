"""
LLM response parser for Signal extraction.

parse_response(raw: str) -> dict

Input : raw string returned by LLMClient.complete()
Output: validated dict with keys: category, urgency, confidence, risk_flags

Raises:
    json.JSONDecodeError — if the response cannot be parsed as JSON even after
                           stripping markdown code fences.
    ValueError           — if the parsed object is missing required keys or
                           contains values outside the allowed domains.
"""

import json
import re

_VALID_CATEGORIES = frozenset({"technical", "billing", "complaint", "general", "other"})
_VALID_FLAGS = frozenset({"complaint", "legal", "pii", "system_error", "critical", "security"})

# Strip ```json ... ``` or ``` ... ``` wrappers that some models add
_FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```", re.IGNORECASE)


def parse_response(raw: str) -> dict:
    """
    Parse and validate the LLM JSON response.

    Unknown category values are normalised to "general".
    Unknown risk_flag tokens are silently dropped.
    Numeric fields are clamped to [0.0, 1.0].
    """
    cleaned = _FENCE_RE.sub("", raw).strip()
    data = json.loads(cleaned)  # raises json.JSONDecodeError on bad JSON

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    # ── category ─────────────────────────────────────────────────────────────
    category = str(data.get("category", "general")).lower().strip()
    if category not in _VALID_CATEGORIES:
        category = "general"

    # ── urgency ──────────────────────────────────────────────────────────────
    try:
        urgency = float(data["urgency"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Missing or invalid 'urgency' in LLM response: {data!r}")
    urgency = round(max(0.0, min(1.0, urgency)), 3)

    # ── confidence ───────────────────────────────────────────────────────────
    try:
        confidence = float(data["confidence"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Missing or invalid 'confidence' in LLM response: {data!r}")
    confidence = round(max(0.0, min(1.0, confidence)), 3)

    # ── risk_flags ───────────────────────────────────────────────────────────
    raw_flags = data.get("risk_flags", [])
    if not isinstance(raw_flags, list):
        raw_flags = []
    risk_flags = sorted(f for f in raw_flags if isinstance(f, str) and f in _VALID_FLAGS)

    return {
        "category":   category,
        "urgency":    urgency,
        "confidence": confidence,
        "risk_flags": risk_flags,
    }
