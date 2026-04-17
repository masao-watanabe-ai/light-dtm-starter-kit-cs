"""
Prompt builder for Signal extraction.

build_prompt(inquiry_text) -> (system_prompt, user_prompt)

The LLM is asked to return a JSON object with four fields:
  category   : str   — one of the defined categories
  urgency    : float — 0.0 (not urgent) to 1.0 (extremely urgent)
  confidence : float — 0.0 (very uncertain) to 1.0 (highly certain)
  risk_flags : list  — zero or more of the defined risk flag tokens
"""

_SYSTEM_PROMPT = """\
You are a customer support signal classifier.
Analyse the inquiry text and return a JSON object with exactly these fields:

  "category":   one of "technical" | "billing" | "complaint" | "general" | "other"
  "urgency":    float 0.0–1.0  (0 = not time-sensitive, 1 = extremely urgent)
  "confidence": float 0.0–1.0  (0 = inquiry is vague/incomplete, 1 = very clear)
  "risk_flags": array of zero or more strings, chosen only from:
                ["complaint", "legal", "pii", "system_error", "critical", "security"]

Guidelines:
- urgency    reflects how time-sensitive resolution is.
- confidence reflects how clearly and completely the inquiry is described.
- risk_flags should only include tokens clearly indicated by the text.
- Return ONLY the JSON object. No markdown, no explanation, no extra keys.\
"""


def build_prompt(inquiry_text: str) -> tuple[str, str]:
    """
    Return (system_prompt, user_prompt) for the signal extraction task.

    Args:
        inquiry_text: Raw inquiry text from the customer.

    Returns:
        Tuple of (system_prompt, user_prompt) to pass to LLMClient.complete().
    """
    user_prompt = f"Inquiry:\n{inquiry_text.strip()}"
    return _SYSTEM_PROMPT, user_prompt
