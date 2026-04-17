from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "light-dtm-starter"
    debug: bool = False
    log_level: str = "INFO"
    trace_store_path: str = "traces/traces.jsonl"

    # ── LLM (OpenAI-compatible) ───────────────────────────────────────────────
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_timeout: float = 10.0   # seconds
    llm_enabled: bool = True    # set to false to always use fallback

    # ── Decision Executor ─────────────────────────────────────────────────────
    # decision_mode: "local" | "orchestrator"
    #   local        → LocalExecutor (in-process, no external call)
    #   orchestrator → OrchestratorAdapter (HTTP); falls back to local on error
    decision_mode: str = "local"

    # URL of the external orchestrator's decision endpoint.
    # Required when decision_mode="orchestrator".
    # Example: http://orchestrator.internal/api/decide
    orchestrator_endpoint: str = ""

    # HTTP request timeout for the orchestrator call (seconds).
    orchestrator_timeout: float = 5.0

    # ── Trace Store ───────────────────────────────────────────────────────────
    # trace_mode: "file" | "ledger"
    #   file   → FileTraceStore (local JSONL + exports/; always reliable)
    #   ledger → LedgerAdapter (HTTP); falls back to file on any error
    trace_mode: str = "file"

    # Base URL of the external ledger service.
    # Required when trace_mode="ledger".
    # Example: http://ledger.internal/api
    # Endpoints used:
    #   POST {ledger_endpoint}/traces  — persist a single trace
    #   GET  {ledger_endpoint}/traces  — retrieve all traces
    ledger_endpoint: str = ""

    # HTTP request timeout for ledger calls (seconds).
    ledger_timeout: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
