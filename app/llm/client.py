"""
OpenAI-compatible LLM client.

Reads configuration from Settings (app/config.py):
  OPENAI_API_KEY   — required; set via env var or .env file
  OPENAI_API_BASE  — default: https://api.openai.com/v1
  OPENAI_MODEL     — default: gpt-4o-mini
  LLM_TIMEOUT      — request timeout in seconds (default: 10.0)

Any API endpoint that accepts POST /chat/completions with the OpenAI message
schema (e.g. Azure OpenAI, local Ollama, vLLM) is compatible.
"""

import httpx

from app.config import settings


class LLMClient:
    def __init__(self) -> None:
        self._api_key = settings.openai_api_key
        self._api_base = settings.openai_api_base.rstrip("/")
        self._model = settings.openai_model
        self._timeout = settings.llm_timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call /chat/completions and return the assistant message content as a string.

        Raises:
            ValueError      — if OPENAI_API_KEY is not configured
            httpx.HTTPError — on non-2xx HTTP responses
            httpx.TimeoutException — if the request exceeds llm_timeout seconds
        """
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        response = httpx.post(
            f"{self._api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
