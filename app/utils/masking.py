import re


def mask_pii(text: str) -> str:
    """Replace email addresses with a placeholder."""
    return re.sub(r"[\w.+-]+@[\w-]+\.[a-zA-Z]+", "[EMAIL]", text)
