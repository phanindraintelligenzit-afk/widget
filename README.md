# DPI-LS — Digital FTE Performance Index

Score any AI agent in real time on a 0–100 index across 7 performance dimensions,
with hard compliance gates and a live embeddable dashboard.

The pitch: *"two lines of code — I'll score your agent live."*

The design rationale, hard requirements, and the full scoring spec live in
[CLAUDE.md](./CLAUDE.md). This README is the runbook.

---

## What's new — `dpi_ls` instrumentation package

On top of the original FastAPI scoring engine, this repo now ships a
**Python instrumentation package** (`dpi_ls/`) that lets you monitor any
AI agent with two lines of code:

```python
import dpi_ls

collector = dpi_ls.monitor(agent, agent_id="my-agent", human_baseline=1)
# ... run your agent normally ...
```

`dpi_ls.monitor()` auto-detects the framework, installs hooks, boots the
dashboard in a background thread, and POSTs the final `AgentObservation`
to `/ingest` on exit — using the **exact same `engine/` scoring math**
as the REST API. No scoring logic is duplicated.

---

## Quick start

Requires Python 3.11+, `uv` (or `pip`).

```bash
git clone <repo-url> dpi-ls
cd dpi-ls

# Install everything (runtime + dev deps)
uv sync          # or: pip install -e ".[dev]"
```

### Option A — run the demo dashboard only

```bash
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Seed the board with fixture data:

```bash
./scripts/demo_seed.sh
```

Open **http://localhost:8000/** — redirects to the live demo at `/widget/demo.html`.

### Option B — run the example agent (end-to-end)

Requires AWS credentials with Bedrock access (`AWS_ACCESS_KEY_ID`, etc.):

```bash
uv run examples/test_agent.py
```

This starts the dashboard automatically, runs the Chandra FinOps agent,
evaluates Q with a LangGraph LLM evaluator, and POSTs the scored
observation. Expected final score: **95–99 / 100, band: Exceptional**.

---

## The `dpi_ls` package

### `dpi_ls.monitor()` — two-line integration

```python
import dpi_ls

collector = dpi_ls.monitor(
    agent,                    # any supported framework object
    agent_id="chandra-finops",
    agent_name="Chandra FinOps Agent",   # optional
    human_baseline=1,         # outputs a human would produce per period
    post=True,                # POST to /ingest on exit (default)
    open_browser=False,       # pop the dashboard tab
    host="127.0.0.1",
    port=8000,
)
```

**`human_baseline`** is the key parameter for **P (Productivity)**:
- Single-run report agent → `human_baseline=1`
- Batch ticket-processing agent handling 100 tickets → `human_baseline=100`
- Defaults to `100` on first run (stored in the DB per agent)

### `dpi_ls.evaluate_quality()` — explicit Q scoring

```python
from dpi_ls import evaluate_quality

outputs = collector.outputs_for_q()   # returns agent prose outputs only
q = evaluate_quality(outputs)          # runs LangGraph LLM evaluator
collector.set_quality(q.accuracy, q.consistency, q.hallucination_rate)
```

Falls back to a deterministic heuristic if the LLM is unreachable.

### Supported frameworks

| Framework | Auto-detected via |
|---|---|
| **OpenAI Agents SDK** | `agents.Agent` instance |
| **LangGraph** | compiled `StateGraph` |
| **LangChain** | `Runnable` / `Chain` |
| **CrewAI** | `Crew` instance |
| **AutoGen** | `ConversableAgent` |
| **Raw OpenAI client** | `openai.OpenAI` / `AsyncOpenAI` |
| **Raw Anthropic client** | `anthropic.Anthropic` |
| **Unknown** | best-effort fallback |

---

## Data flow — how `dpi_ls` uses the project's engine

```
Your agent code
    │
    │  dpi_ls.monitor() installs framework hooks
    │  hooks → collector.record_llm_call() / record_tool_call()
    │
    ↓  atexit: poster.post_observation()
    │
    │  POST http://127.0.0.1:8000/ingest?baseline=N
    │        body: canonical AgentObservation (contract/models.py)
    ↓
api/app.py → api/scoring.py
    │
    ├── engine/metrics.py   compute_P, Q, E, G, R, V, C    ← project engine
    ├── engine/score.py     rate() weighted geometric mean  ← project engine
    ├── engine/gates.py     G/R/V compliance gates          ← project engine
    ├── engine/bands.py     Exceptional / Strong / …        ← project engine
    ├── contract/models.py  AgentObservation schema         ← project contract
    └── store/repo.py       upsert_agent, save_score        ← project store
```

**`dpi_ls` contains zero scoring math.** It is purely a signal collector
and poster. All 7 metric computations happen in `engine/` exactly as they
do for the REST API and the webhook adapters.

---

## The DPI-LS score

Each sub-metric normalises to [0, 1]:

| Metric | Formula | What `dpi_ls` measures |
|---|---|---|
| **P** — Productivity | `min(1, agent_runs / human_baseline)` | Completed agent runs vs human_baseline |
| **Q** — Quality | `0.70·Acc + 0.20·Con + 0.10·(1−Hal)` | LangGraph LLM evaluator over agent prose outputs |
| **E** — Execution | `successful_calls / attempts` | LLM + tool call success rate |
| **G** — Governance | `1 − (violations / total_actions)` | Policy scan on every output (PII, auth errors, etc.) |
| **R** — Risk | `1 − min(1, Σ(freq×sev) / R_max)` | Recorded incidents / errors |
| **V** — Validation | `validated / required` | Structured outputs: JSON, Markdown with `##` headers or `\| tables \|` |
| **C** — Cost | `min(1, human_cost / AI_cost) × utilization` | Token-estimated cost vs human_cost_per_output |

Composite — weighted geometric mean:

```
DPI-LS = 100 · ( P^0.15 · Q^0.20 · E^0.15 · G^0.20 · R^0.15 · V^0.10 · C^0.05 )
```

**Hard compliance gates.** If `G < 0.60` OR `R < 0.50` OR `V < 0.60`,
the score is capped at 69 (top of *Needs Optimization*) and flagged `unsafe=true`.

**Bands.** `85–100 Exceptional · 70–84 Strong · 50–69 Needs Optimization · <50 Underperforming`

---

## API surface

All endpoints return JSON. CORS is `*` by default for the demo —
set `WIDGET_ALLOWED_ORIGINS=https://a.com,https://b.com` to tighten.

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness probe |
| GET | `/` | Redirects to `/widget/demo.html` |
| GET | `/adapters` | Registered full-observation adapters |
| GET | `/sources` | Registered source adapters |
| POST | `/ingest` | Body: canonical `AgentObservation`. Optional `?baseline=N` updates the agent's human_output_per_period before scoring. |
| POST | `/ingest/{adapter_name}` | Adapter-specific payload (OTel spans, webhook:acme, …) |
| POST | `/ingest/source/{name}` | Source partial payload. Merged per agent, then scored. |
| GET | `/ratings` | Board view — one row per agent, latest score |
| GET | `/agents` | List all known agents |
| GET | `/agents/{id}/score` | Latest `Rating` (score, band, gate failures, all 7 metrics) |
| GET | `/agents/{id}/history` | Newest-first score history |
| GET / PUT | `/settings` | Get / replace tunables (`Settings`) |
| POST | `/sme-flow/start` | Begin conversational quality capture |
| POST | `/sme-flow/{session_id}/respond` | Next SME prompt step |
| POST | `/agents/{id}/sme-rating` | Direct SME rating (audit-only) |
| GET | `/widget/dpi-ls.js`, `/widget/demo.html` | Static widget bundle |

OpenAPI / Swagger UI: **http://localhost:8000/docs**

### `POST /ingest?baseline=N`

The `baseline` query parameter is how `dpi_ls.monitor()` passes
`human_baseline` through to the engine without modifying the
`AgentObservation` contract:

```bash
curl -X POST "http://localhost:8000/ingest?baseline=1" \
     -H "Content-Type: application/json" \
     -d @observation.json
```

This updates `AgentRow.baseline_human_output` in the DB before scoring,
so P is computed against the right denominator on every subsequent ingest.

---

## Onboarding a new agent or source

### Path 1 — the source emits a complete observation

POST a canonical `AgentObservation` directly. No code needed:

```bash
curl -X POST http://localhost:8000/ingest \
     -H 'Content-Type: application/json' \
     -d @observation.json
```

For non-canonical JSON shapes, write a YAML field mapping and drop it into
`MAPPINGS_DIR`. The bootstrap auto-registers it as `webhook:<source>`.
See `fixtures/mapping_acme.yaml` for the full mapping syntax.

### Path 2 — the source only knows one dimension

Write a `SourceAdapter` that returns `list[PartialObservation]`. The API
merges latest-per-dimension across all partials before scoring.
See `ingestion/sources/` — each adapter is under 80 lines.

### Path 3 — instrument an agent directly (new)

```python
import dpi_ls

collector = dpi_ls.monitor(agent, agent_id="my-agent", human_baseline=1)
# run your agent
result = await Runner.run(agent, "your prompt")
```

That's it. The package handles framework detection, hook installation,
Q evaluation, and posting to the dashboard.

---

## Configuration

| Env var | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./dpi_ls.db` | SQLAlchemy URL. Use `postgresql+psycopg2://…` in prod. |
| `MAPPINGS_DIR` | (unset) | Folder scanned at startup for `mapping_*.yaml`. |
| `WIDGET_ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowlist. |
| `MODEL_NAME` / `BEDROCK_MODEL_ID` | `us.amazon.nova-pro-v1:0` | Bedrock model for Q LLM evaluator. |
| `AWS_DEFAULT_REGION` / `AWS_REGION` | (boto3 default chain) | AWS region for Bedrock. |
| `DPI_LS_DATABASE_URL` | same as `DATABASE_URL` | Override DB URL for the embedded server only. |

Per-deployment tunables (weights, gate thresholds, R_max, etc.) live in
the `settings` DB table — fetch/write via `GET /settings` and `PUT /settings`.

---

## Running the tests

```bash
uv run pytest           # or: pytest
```

**180 tests, < 7 seconds.** All pass. Key test files:

| File | What it covers |
|---|---|
| `tests/test_engine_reference.py` | 4 spec reference outputs — if these break, the engine is wrong |
| `tests/test_dpi_ls_collector.py` | SignalCollector: record_llm_call, record_agent_run, outputs_for_q, to_observation |
| `tests/test_dpi_ls_frameworks.py` | `_safe_text`, `_safe_iter_tokens`, patcher idempotency |
| `tests/test_dpi_ls_end_to_end.py` | Full monitor() → POST /ingest → score round-trip |
| `tests/test_api_*.py` | FastAPI routes, ingest, settings, SME flow |
| `tests/test_ingestion_*.py` | Webhook adapter, OTel, source adapters |

---

## Repo layout

```
contract/           Pydantic models — AgentObservation, PartialObservation
engine/             PURE scoring. No I/O. Never edit.
  metrics.py        compute_P, Q, E, G, R, V, C
  score.py          rate() — weighted geometric mean + gate + band
  gates.py          G/R/V hard compliance gates
  bands.py          Exceptional / Strong / Needs Optimization / Underperforming
  sme_flow.py       Conversational Q state machine
ingestion/
  generic/          GenericWebhookAdapter (YAML mapping) + OTelAdapter
  sources/          aws_cost, puvi_noise, arize, servicenow, jira + stubs
api/                FastAPI app, routes, orchestration, bootstrap
  app.py            All route handlers
  scoring.py        score_and_persist() — the bridge between API and engine
  bootstrap.py      Adapter registration, DB init
store/              SQLAlchemy models + repo
  models.py         AgentRow, ObservationRow, ScoreRow, SettingsRow, …
  repo.py           upsert_agent, save_observation, save_score, get_settings
dpi_ls/             Instrumentation package — two-line agent monitoring
  __init__.py       Public API: monitor(), evaluate_quality()
  monitor.py        Entry point — framework detection, server boot, atexit
  collector.py      SignalCollector — accumulates P/Q/E/G/R/V/C signals
  evaluator.py      LangGraph Q evaluator (accuracy, consistency, hallucination)
  heuristics.py     Deterministic Q fallback when LLM is unreachable
  poster.py         post_observation() — POSTs AgentObservation to /ingest
  server.py         Background uvicorn launcher (idempotent, daemon thread)
  policy.py         Deterministic G policy scan (PII, auth errors, …)
  _state.py         Process-wide collector singleton
  frameworks/       Framework-specific patchers
    base.py         BasePatcher, _safe_text, _safe_iter_tokens
    openai_agents.py  OpenAI Agents SDK (Runner.run hooks + agent run counter)
    langchain.py    LangChain Runnable wrapper
    langgraph.py    LangGraph compiled graph wrapper
    crewai.py       CrewAI Crew wrapper
    autogen.py      AutoGen ConversableAgent wrapper
    raw_openai.py   Raw openai.OpenAI / AsyncOpenAI client
    raw_anthropic.py  Raw anthropic.Anthropic client
    unknown.py      Best-effort fallback for unrecognized objects
widget/             dpi-ls.js (vanilla web components) + demo.html
fixtures/           Synthetic payloads used by tests and the demo seed
tests/              180 tests
examples/
  test_agent.py     End-to-end Chandra FinOps agent (OpenAI Agents + Bedrock)
scripts/
  demo_seed.sh      Seeds the board with fixture data
```

---

## Key implementation notes

### V — Validation scoring

`_looks_structured()` recognises the following as validated outputs:

- Pure JSON object `{ … }` or array `[ … ]`
- XML semantic tags: `<answer>`, `<result>`, `<response>`, `<output>`
- Markdown fenced code blocks: ` ```json … ``` `
- **Markdown section headers anywhere in the text**: `## …` or `### …`
- **Markdown tables anywhere in the text**: `| col | col |`

Note: tool results (raw API JSON) are captured for V/G scoring but are
**not** sent to the Q LLM evaluator — the LLM cannot verify factual
accuracy of raw API data.

### Q — Quality evaluation

The LangGraph evaluator runs three sequential LLM nodes:

1. **Accuracy** — does the agent's analysis correctly reflect the tool data?
2. **Consistency** — is the reasoning internally coherent?
3. **Hallucination** — what fraction of claims in the analysis have no basis in the data?

Only **agent prose outputs** (not raw tool results) are sent to the evaluator.
Falls back to `heuristics.py` if the LLM is unreachable.

### P — Productivity

P measures **agent-level runs**, not individual LLM calls within a run:

```
P = min(1, agent_runs_completed / human_baseline)
```

For a single-run report agent: `human_baseline=1` → `P = 1.0`.
For a batch agent processing 100 tasks: `human_baseline=100`.

### Port reuse

If you start `uvicorn api.app:app` manually before running an instrumented
agent script, `dpi_ls` automatically detects the running server and reuses
it silently instead of trying (and failing) to bind the same port.

---

## What's intentionally not done

- **No auth.** Anyone who can reach the API can POST observations or PUT settings.
- **Live source connectors** (boto3 HTTP fetch, ServiceNow REST, Jira REST) aren't wired.
  The source adapters accept the JSON shapes those systems produce; the
  HTTP fetch layer is the next milestone.
- **`langgraph`, `bedrock`, `ray`, `bmc`, `sap_hr`** source adapters are stubs
  that register and return `[]`.
- No Dockerfile, no Alembic migrations, no rate limiting, no metrics export.
- Agent marketplace, multi-tenant onboarding, billing — parked per the spec.

The pieces that *are* done — the engine, the contract, the ingestion pattern,
the `dpi_ls` package, the widget — were built to make any of the above
incremental: a real AWS adapter is "fill in the fetch step," not a rewrite.
