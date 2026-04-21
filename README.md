# Light DTM Starter Kit (Customer Support)

A minimal, runnable decision pipeline for customer support inquiries.
It classifies an inquiry into a structured decision — route, action, and state — using
signal extraction and YAML-based rules, with full trace logging.
No LLM or external service is required to start.

---

## What this system does

- Receives a customer support inquiry (text + optional metadata).
- Extracts a **signal** from it: urgency score, confidence score, and risk flags.
- Matches that signal against a set of **declarative rules** (YAML).
- Returns a structured **decision**: where to route it, what action to take, and what state it's in.
- Logs every run as a **trace** — both a running JSONL log and a per-run JSON snapshot.

The goal is a predictable, auditable baseline that can be extended with an LLM or
orchestration system later — without rewriting the core pipeline.

---

## Why this exists — Signal ≠ Decision

A common mistake in support automation is treating the raw text of an inquiry as the
decision input. This system separates two concerns:

| Layer | Question | Output |
|---|---|---|
| **Signal** | *What is actually happening here?* | urgency, confidence, risk_flags |
| **Decision** | *What should we do about it?* | route, action, decision_state |

The signal is extracted first, then the decision is made against the signal — not the
raw text. This separation means:

- Rules stay readable and testable (they match numbers and flags, not strings).
- The signal layer can be swapped for an LLM without touching the rule or decision layer.
- Every decision is traceable back to the signal values that produced it.

---

## Architecture

```
Inquiry (text, category, priority, risk_flags)
  │
  ▼
PreprocessService          — normalize and clean the inquiry text
  │
  ▼
SignalService               — extract structured signal from the inquiry
  │  urgency     : 0.0–1.0  (derived from priority + keyword detection)
  │  confidence  : 0.0–1.0  (derived from text length + category presence)
  │  risk_flags  : []        (complaint, legal, pii, system_error, critical, security)
  │
  ▼
RuleLoader + _match_rule   — evaluate signal against decision_rules.yaml
  │  first matching rule wins; empty condition = catch-all
  │
  ▼
LocalExecutor              — execute(signal, context) → Decision
  │  route          : auto | human | hold
  │  action         : reply | assign_queue | escalate | none
  │  decision_state : completed | requires_human | waiting
  │  applied_rule   : rule identifier (machine-readable)
  │  reason         : explanation (human-readable)
  │
  ▼
FileTraceStore
  ├── traces/traces.jsonl          — append-only JSONL log of all runs
  └── traces/exports/{id}_{ts}.json— full pipeline snapshot per run
  │
  ▼
DecisionResult             — returned to the caller via /api/decision/run
```

**Adapter swap points** (without touching the pipeline):

```
LocalExecutor      →  OrchestratorAdapter   (external workflow system)
FileTraceStore     →  LedgerAdapter          (external audit log / ledger)
SignalService      →  LLM-based extraction   (replace heuristics with a model call)
```

---

## Quick Start

### Local

```bash
# Requires Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
# → http://localhost:8000
```

### Docker

```bash
docker compose up --build
# → http://localhost:8000
```

Traces are written to `./traces/` on the host (volume-mounted).

---

## Configuration

Copy `.env.example` to `.env` and edit as needed before starting the server.

```bash
cp .env.example .env
```

All variables have defaults that work out of the box — you only need to set the ones
you want to change.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | _(blank)_ | Enables LLM signal extraction. Leave blank to use keyword heuristics. |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model used for LLM signal extraction |
| `LLM_ENABLED` | `true` | Set to `false` to always use fallback heuristics |
| `DECISION_MODE` | `local` | `local` = in-process; `orchestrator` = external HTTP |
| `ORCHESTRATOR_ENDPOINT` | _(blank)_ | Required when `DECISION_MODE=orchestrator` |
| `TRACE_MODE` | `file` | `file` = local JSONL; `ledger` = external HTTP |
| `TRACE_STORE_PATH` | `traces/traces.jsonl` | Path for the local JSONL log |
| `LEDGER_ENDPOINT` | _(blank)_ | Required when `TRACE_MODE=ledger` |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, …) |

---

## Testing

```bash
python -m pytest
```

Tests cover: signal extraction heuristics, trace model serialization, file trace store
(save / list / export), local executor rule mapping, and view model construction.

```
tests/
  test_signal.py           SignalService fallback heuristics (urgency, confidence, risk_flags)
  test_trace.py            Trace model creation and JSON round-trip
  test_trace_store.py      FileTraceStore save / list_all / save_export
  test_decision_executor.py LocalExecutor rule mapping and defaults
  test_view_model.py       ViewModelService context builder
```

---

## Demo

Open **http://localhost:8000/demo** in a browser.

- Enter inquiry text and select a priority (0–10).
- Optionally check explicit risk flags (complaint, legal, pii, …).
- Click **Run Decision**.
- The result panel shows: route badge, action, decision state, applied rule,
  reason, confidence bar, risk flags, signal ID, and trace ID.

No JavaScript framework or build step — plain HTML with a `fetch` call.

---

## API

### Health check

```
GET /health
→ {"status": "ok"}
```

### Run the decision pipeline

```
POST /api/decision/run
Content-Type: application/json
```

**Request**

```json
{
  "id": "inq-001",
  "text": "Our payment system stopped responding 10 minutes ago.",
  "category": "technical",
  "priority": 7
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | unique inquiry identifier |
| `text` | string | yes | raw inquiry text |
| `category` | string | no | technical, billing, complaint, general |
| `priority` | int 0–10 | no | contributes to urgency computation |
| `urgency` | float 0–1 | no | explicit override; skips heuristic |
| `confidence` | float 0–1 | no | explicit override; skips heuristic |
| `risk_flags` | string[] | no | explicit flags merged with detected ones |

**Response**

```json
{
  "inquiry_id": "inq-001",
  "route": "auto",
  "action": "escalate",
  "decision_state": "completed",
  "applied_rule": "critical_risk_escalate",
  "reason": "High-risk flags detected (system_error, critical, or security). Automatically forwarded to an upstream high-priority queue — no human agent assigned.",
  "confidence": 0.95,
  "risk_flags": ["system_error"],
  "signal_id": "3f8a1c2d-...",
  "trace_id": "7b4e9a0f-...",
  "executed_at": "2026-04-17T04:32:26.478738"
}
```

Interactive docs: **http://localhost:8000/docs** (Swagger UI)

---

## Decision Model

Every decision is described by three orthogonal fields.

### `route` — where it goes

| Value | Meaning |
|---|---|
| `auto` | Handled by an automated system; no human agent assigned |
| `human` | Requires human agent review |
| `hold` | No action yet; awaiting additional context |

### `action` — what happens

| Value | Meaning |
|---|---|
| `reply` | Automated reply is sent to the customer |
| `assign_queue` | Placed in a human review queue |
| `escalate` | Forwarded to an upstream high-priority queue (automated — **not** a human) |
| `none` | No action taken |

> **Note on `route=auto, action=escalate`**
> This combination means the inquiry is *automatically* forwarded to a higher-priority
> processing system — not to a human agent. It is distinct from `route=human`,
> which always implies human involvement.

### `decision_state` — lifecycle status

| Value | Meaning |
|---|---|
| `completed` | The decision was executed; no further action required |
| `requires_human` | A human must act before the inquiry can proceed |
| `waiting` | Held; the system will re-evaluate when more context arrives |

### `applied_rule` and `reason`

| Field | Purpose | Example |
|---|---|---|
| `applied_rule` | Machine-readable rule identifier — use for filtering and audit | `"low_confidence_hold"` |
| `reason` | Human-readable explanation — use for display and debugging | `"Signal confidence is below the threshold (< 0.35)..."` |

These are always different: `applied_rule` is the ID, `reason` is the explanation.

---

## Rule System

Rules live in `app/rules/decision_rules.yaml`. They are evaluated top-to-bottom;
the first matching rule wins.

```yaml
rules:
  - name: critical_risk_escalate
    reason: >-
      High-risk flags detected. Forwarded to upstream queue automatically.
    condition:
      risk_flags_any: ["system_error", "critical", "security"]
    route: auto
    action: escalate
    decision_state: completed
    base_confidence: 0.95
```

**Available condition keys**

| Key | Type | Matches when… |
|---|---|---|
| `urgency_gte` | float | `signal.urgency >= value` |
| `confidence_gte` | float | `signal.confidence >= value` |
| `confidence_lt` | float | `signal.confidence < value` |
| `risk_flags_any` | string[] | at least one flag is present |
| `risk_flags_all` | string[] | all flags are present |
| _(empty `{}`)_ | — | always matches (catch-all) |

**Two confidence values — do not confuse them**

- `condition.confidence_lt` — the *signal* confidence threshold that triggers the rule.
- `base_confidence` — the *decision* confidence: how certain the system is that this
  decision is correct. These are independent values.

To add a rule: append a new entry to the YAML. No code change required.

---

## Trace

Every pipeline run writes two artifacts.

### `traces/traces.jsonl` — running log

One JSON object per line, appended on every run.

```json
{
  "trace_id": "7b4e9a0f-...",
  "inquiry_id": "inq-001",
  "step": "decision_run",
  "trace_version": "1.0",
  "timestamp": "2026-04-17T04:32:26.478738",
  "applied_rule": "critical_risk_escalate",
  "reason": "High-risk flags detected...",
  "decision_path": [
    "preprocess",
    "signal_extract",
    "rule_match:critical_risk_escalate",
    "execute"
  ],
  "executor_mode": "local",
  "trace_store_mode": "file",
  "payload": {
    "signal_id": "...",
    "urgency": 0.7,
    "confidence": 0.7,
    "risk_flags": ["system_error"],
    "route": "auto",
    "action": "escalate",
    "decision_state": "completed"
  }
}
```

### `traces/exports/{inquiry_id}_{timestamp}.json` — per-run snapshot

Full pipeline dump: inquiry → signal → decision → trace ID.
Useful for offline debugging and audit.

**`decision_path`** records every step taken in order:
`preprocess → signal_extract → rule_match:{rule_name} → execute`

---

## Extension

The system is designed so each layer can be replaced independently.

### Add an LLM to signal extraction

Replace `SignalService.to_signal()` with a call to an LLM.
The rest of the pipeline — rules, executor, trace — does not change.

```python
# app/services/signal_service.py
class SignalService:
    def to_signal(self, inquiry: Inquiry, source: str = "api") -> Signal:
        # swap this block for an LLM call:
        response = llm_client.extract(inquiry.text)
        return Signal(
            urgency=response.urgency,
            confidence=response.confidence,
            risk_flags=response.risk_flags,
            ...
        )
```

### Connect an external orchestrator

Swap `LocalExecutor` for `OrchestratorAdapter` in `DecisionPipelineService.__init__`:

```python
# app/services/decision_pipeline.py
from integrations.decision_executor.orchestrator_adapter import OrchestratorAdapter

self._executor = OrchestratorAdapter()
```

Implement `OrchestratorAdapter.execute()` to call your workflow system.
The `BaseDecisionExecutor` interface is `execute(signal, context) → Decision`.

### Connect an external audit ledger

Swap `FileTraceStore` for `LedgerAdapter` in `DecisionPipelineService.__init__`:

```python
from integrations.trace_store.ledger_adapter import LedgerAdapter

self._store = LedgerAdapter()
```

Implement `LedgerAdapter.save()` and `LedgerAdapter.list_all()` to write to your ledger.
The `BaseTraceStore` interface is minimal by design.

---

## Project Layout

```
app/
  main.py                  FastAPI app, /health endpoint
  config.py                pydantic-settings configuration
  models/
    inquiry.py             Input model
    signal.py              Extracted signal (urgency, confidence, risk_flags)
    decision.py            Decision (route, action, decision_state, applied_rule, reason)
    decision_result.py     API response model
    trace.py               Trace record
  routes/
    decision_run.py        POST /api/decision/run
    demo_view.py           GET  /demo
    ingest.py              POST /ingest/  (stub)
    decision.py            GET  /decision/ (stub)
    trace.py               GET  /trace/   (stub)
  services/
    decision_pipeline.py   Pipeline orchestration
    signal_service.py      Signal extraction heuristics
    preprocess_service.py  Text normalization
    rule_loader.py         YAML rule loader
    action_service.py      (stub)
    human_gate_service.py  (stub)
    view_model_service.py  (stub)
  rules/
    decision_rules.yaml    Decision rules
  templates/
    demo.html              Single-page demo UI
  llm/
    client.py              LLM client stub
    parser.py              LLM response parser stub
    prompt_builder.py      Prompt builder stub

integrations/
  decision_executor/
    base.py                BaseDecisionExecutor (ABC)
    local_executor.py      In-process executor (default)
    orchestrator_adapter.py External orchestrator stub
  trace_store/
    base.py                BaseTraceStore (ABC)
    file_store.py          JSONL + per-run JSON export (default)
    ledger_adapter.py      External ledger stub

traces/
  traces.jsonl             Append-only run log
  exports/                 Per-run JSON snapshots
```

---

## Stack

| Component | Library | Version |
|---|---|---|
| Web framework | FastAPI | 0.115 |
| ASGI server | Uvicorn | 0.30 |
| Data models | Pydantic v2 | 2.8 |
| Templates | Jinja2 | 3.1 |
| Rules | PyYAML | 6.0 |
| Config | pydantic-settings | 2.4 |
| Runtime | Python | 3.11 |

## Learn More

- Light DTM Starter Kit  
  https://deus-ex-machina-ism.com/en/light-dtm-minimum-decision-ai-starter-kit/
