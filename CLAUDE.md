# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**DPI-LS** scores **any AI agent** in real time on a 0–100 index across 7 performance dimensions (P, Q, E, G, R, V, C) with hard compliance gates, and ships an embeddable widget that shows the live score. Python 3.11+. Two surfaces:

- **Server** — FastAPI + SQLAlchemy. POST observations in, GET the board out. Hosts the widget bundle.
- **`dpi_ls` package** — 2-line integration for any agent (`import dpi_ls; dpi_ls.monitor(agent, agent_id="...")`). Auto-detects framework, installs hooks, posts the canonical observation on `atexit`.

The 1200-line `README.md` is the runbook (framework recipes, mermaid diagrams, full API surface, env var table, configuration). **Read CLAUDE.md first for orientation; reach for README.md when you need a specific framework recipe or wire format.**

### See the demo in 3 commands

```bash
uv sync
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000   # in one terminal
./scripts/demo_seed.sh                                   # in another (waits for /healthz)
```

Then open **http://localhost:8000/** in a browser — the root redirects to `/widget/demo.html`, the live board + per-agent card with three seeded agents (`agent-strong`, `agent-baseline`, `agent-unsafe`) and the multi-source story for `agent-multi-001`. The board polls every 3 s.

---

## Operator's quick start

```bash
# Install (uses uv)
uv sync

# Run the full test suite (302 tests, < 12 s)
uv run pytest

# Run a single test file
uv run pytest tests/test_engine_reference.py -v

# Run a single test
uv run pytest tests/test_engine_formulas.py::test_specific_name -xvs

# Start the dashboard locally (binds 0.0.0.0:8000)
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000

# Seed the dashboard with fixtures (wait for /healthz first)
./scripts/demo_seed.sh

# Manual health check
curl -s http://localhost:8000/healthz
```

The Windows bash here is MSYS/Git-Bash; use forward slashes and Unix-style commands (`/dev/null`, not `NUL`).

There is no separate linter config — `pyproject.toml` is just the build manifest. The venv is at `.venv/`. On Windows, the python binary is `.venv/Scripts/python.exe`; on Linux/macOS, `.venv/bin/python`. Prefer `uv run` so the venv is implicit.

---

## The cardinal invariant (the one rule)

**The engine consumes only `contract.AgentObservation`. It never imports an agent framework, an HTTP client, a database, or any adapter.** This is what makes the system agent-agnostic.

- ✅ Onboarding a new agent = write a new `Adapter`/`SourceAdapter` in `ingestion/`, or drop a YAML mapping in `MAPPINGS_DIR`.
- ❌ Onboarding a new agent ≠ modify `engine/`, `contract/`, or the score math.

If a future change touches `engine/` to support a new agent, that is by definition the wrong change. The engine is the source of truth; everything else is plumbing.

---

## Layer boundaries (import rules)

| Layer | May import from | May NOT import from |
|---|---|---|
| `engine/` | `contract/` only | anything else (no adapters, no frameworks, no FastAPI, no SQLAlchemy) |
| `contract/` | stdlib, pydantic | adapters, frameworks, FastAPI, SQLAlchemy |
| `ingestion/` | `contract/`, stdlib, third-party clients of the source system | `engine/`, `store/`, `api/`, `dpi_ls/` |
| `store/` | `contract/`, SQLAlchemy | `engine/`, `ingestion/`, `api/`, `dpi_ls/` |
| `api/` | `contract/`, `engine/`, `ingestion/`, `store/` | `dpi_ls/` (separate concern) |
| `dpi_ls/` | stdlib, frameworks, `contract/` for the observation schema it POSTs | `engine/`, `store/`, `api/` (it talks to the API over HTTP) |
| `widget/` | nothing in this repo (vanilla JS, served as a static file) | — |

The single permitted cross-layer leak: `api/scoring.py` is the bridge that takes a request, talks to `store/`, then calls `engine/`. Everything else stays one-way.

---

## Architecture (post-M5 state)

```
dpi-ls/
├── contract/         Pydantic models — the only schema the engine sees
│   ├── models.py     AgentObservation, Quality, Cost, Policy, Validation, Executions
│   ├── partial.py    PartialObservation — one dimension at a time, merged per agent
│   ├── rating.py     Rating — the engine's public output (score, band, gates, metrics)
│   └── settings.py   Tunables (weights, gate thresholds, R_max, human cost, baseline)
│
├── engine/           PURE scoring. No I/O. No framework imports.
│   ├── metrics.py    compute_P, Q, E, G, R, V, C  →  7 normalized [0,1] sub-metrics
│   ├── score.py      composite() — weighted geometric mean × 100
│   ├── gates.py      gate_check() — G/R/V compliance floors; cap at 69 if any fire
│   ├── bands.py      band() — Exceptional / Strong / Needs Optimization / Underperforming
│   ├── completeness.py   coverage cap — < 4 dims or any G/R/V missing → Needs Optimization
│   ├── rate.py       rate() — wires composite → gates → bands → completeness into Rating
│   └── sme_flow.py   LangGraph conversational Q-capture state machine (M6)
│
├── ingestion/        Adapters — the only place that knows about agent runtimes
│   ├── base.py            Adapter interface (returns list[AgentObservation])
│   ├── registry.py        Name → adapter lookup
│   ├── generic/           Universal adapters (work for any source)
│   │   ├── webhook.py         GenericWebhookAdapter — POST any JSON
│   │   ├── mapping.py         FieldMapping — YAML field-mapping for arbitrary payloads
│   │   ├── jsonpath.py        JSONPath-lite for the mapping engine
│   │   └── otel.py            OTelAdapter — OTel spans → AgentObservation
│   └── sources/            Per-system partial-dimension adapters (one dim each)
│       ├── base.py            SourceAdapter interface (returns list[PartialObservation])
│       ├── aws_cost.py        → C
│       ├── puvi_noise.py      → G (policy violations)
│       ├── arize.py           → G + Q (Arize Phoenix)
│       ├── bedrock.py         → C + P
│       ├── sap_hr.py          → G
│       ├── audit_trail.py     → G
│       ├── ray.py             → R + E + G
│       ├── servicenow.py      → R
│       ├── bmc.py             → R
│       ├── jira.py            → R
│       ├── langgraph.py       → E
│       ├── stubs.py           ALL_STUBS = () — no stubs remain
│       └── registry.py        source registry
│
├── api/              FastAPI — the demo surface the widget polls
│   ├── app.py            Routes (/ingest, /ratings, /agents/{id}/score, /settings, /sme-flow/*, /sources, /adapters, /widget/*)
│   ├── scoring.py        score_and_persist() — the bridge: API ↔ engine ↔ store
│   ├── bootstrap.py      Adapter registration, DB init, MAPPINGS_DIR scan
│   ├── schemas.py        Request/response models
│   └── sme_orchestration.py   Conversational Q-capture HTTP layer
│
├── store/            SQLAlchemy persistence
│   ├── db.py            Engine + session factory, portable across SQLite/Postgres
│   ├── models.py        AgentRow, ObservationRow, ScoreRow, SettingsRow, PartialObservationRow, ...
│   └── repo.py          upsert_agent, save_observation, save_partial, save_score, get_settings
│
├── dpi_ls/           The 2-line installable package (separate concern from server)
│   ├── monitor.py       Framework detection, server boot, atexit finalizer
│   ├── collector.py     SignalCollector — accumulates P/Q/E/G/R/V/C signals
│   ├── evaluator.py     LangGraph Q evaluator (accuracy, consistency, hallucination)
│   ├── heuristics.py    Deterministic Q fallback when LLM unreachable
│   ├── poster.py        post_observation() — POSTs AgentObservation to /ingest
│   ├── server.py        Background uvicorn launcher (idempotent, daemon thread)
│   ├── policy.py        Multi-engine G policy scanner: Presidio (NLP/PII), detect-secrets, semantic RAG, OPA rules
│   ├── risk.py          Lakera Guard API integration — detects prompt injections, jailbreaks, toxicity in text
│   └── frameworks/      Framework-specific patchers
│       ├── base.py, openai_agents.py, langchain.py, langgraph.py,
│       │   crewai.py, autogen.py, llama_index.py, rag.py,
│       │   raw_openai.py, raw_anthropic.py, unknown.py
│
├── widget/           Embeddable dashboard (vanilla web components, no framework)
│   ├── dpi-ls.js        ~650 lines, two custom elements: <dpi-ls-board> and <dpi-ls-agent>
│   └── demo.html        Standalone demo page
│
├── fixtures/         Sample observations + YAML mappings (mock-first dev)
│   ├── obs_{baseline,strong,unsafe}.json    Canonical 7-dim observations
│   ├── raw_acme_payload.json                Non-canonical payload (mapping target)
│   ├── mapping_acme.yaml, mapping_servicenow.yaml  YAML field-mappings
│   └── source_*.json                        Per-source adapter payloads
│
├── examples/         End-to-end demo agents (one per supported framework)
│   ├── test_agent.py, langgraph_research.py, langchain_qa.py, crewai_research.py,
│   │   autogen_debate.py, llamaindex_rag.py, raw_bedrock.py, run_all.py
│
├── tests/            302 tests, < 12 s. See "Test layout" below.
├── scripts/
│   └── demo_seed.sh   POSTs every fixture through the right ingest path
├── api/bootstrap.py   Auto-registers adapters at startup
├── start.sh           Railway entrypoint (uvicorn api.app:app on $PORT)
├── Dockerfile         Multi-stage build (python:3.11-slim, non-root dpi user)
├── railway.toml       Railway deploy config
└── pyproject.toml     Pydantic v2, FastAPI, SQLAlchemy 2, langgraph, OpenInference; pytest
```

---

## The 7 dimensions

Each sub-metric is normalized to **[0, 1]**. None is a valid value (means "needs input", not zero).

| Dim | Formula | Vacuous default | Source |
|---|---|---|---|
| **P** Productivity | `min(1, AI_output_per_period / human_baseline)` | 0.0 (no baseline) | `tasks.completed` / per-agent `human_baseline` from DB |
| **Q** Quality | `0.7·Accuracy + 0.2·Consistency + 0.1·(1−Hallucination)` | computed | LangGraph LLM evaluator on the last N agent prose outputs |
| **E** Execution | `successful_executions / total_attempts` | 0.0 | LLM + tool call success rate |
| **G** Governance | `1 − policy_violations / total_actions` | **1.0** | Multi-engine policy scan: NLP-based (Presidio), secrets detection, semantic RAG, OPA rules |
| **R** Risk | `1 − min(1, Σ(freq×severity) / R_max)` | **1.0** | Lakera Guard API (prompt injection, jailbreaks, toxicity) + exceptions/incidents |
| **V** Validation | `validated_components / total_required` | **1.0** | JSON / `## headers` / `<answer>` / markdown tables detector |
| **C** Cost | `min(1, human_cost_per_output / AI_cost_per_output) × utilization` | 0.0 / 1.0 (see `engine/metrics.compute_C`) | Token-estimated cost vs `human_cost_per_output` |

**Composite — weighted arithmetic mean of the 7 metrics × 100:**

```
DPI-LS = 100 × ( 0.15·P + 0.20·Q + 0.15·E + 0.20·G + 0.15·R + 0.10·V + 0.05·C )
```

The arithmetic mean expresses "score reflects performance across all
7 metrics" — a 0 in G lowers the score, but doesn't nuke it to zero
(six other dims at 1.0 still drive the score above 0). The safety-net
for a fully-failed dim is the **gate force-cap** (see
"Compliance gates" below) — when G / R / V dips below its floor, the
score is pinned to 69 (top of "Needs Optimization") and `unsafe=True`.

The four reference numbers the engine tests guard:

| Input | Expected output |
|---|---|
| all metrics = 0.85 | composite = 85, band = Exceptional |
| all metrics = 0.92 | composite = 92, band = Exceptional |
| all metrics = 0.55 | raw = 55, G+V gate fires, `score=69`, `unsafe=True`, band = Needs Optimization |
| all 0.85, G = 0.25 | raw = 73, G gate fires, `score=69`, `unsafe=True`, band = Needs Optimization |

These are asserted in `tests/test_engine_reference.py` and `tests/test_engine_formulas.py`. **If any of these break, the engine is wrong** — not the test.

---

## Compliance gates + completeness cap (the two non-obvious behaviors)

These are why a C-only agent doesn't score 100, and why a single PII leak floors the band regardless of how strong everything else is.

**Compliance gates** (`engine/gates.py`): if `G < 0.60` OR `R < 0.50` OR `V < 0.60`, the rating is **capped at 69** and `unsafe=True`. Missing metrics (None) are *deferred*, not failed — the engine never reports a gate violation for a dimension it hasn't observed. This is why a fresh single-source C agent is safe: no G/R/V data → no gate fires.

**Completeness cap** (`engine/completeness.py`): because the composite *redistributes weight* off None metrics, a C-only agent with `C=1.0` would otherwise score `0.9^1.0 × 100 = 90` and read as "Strong". The completeness cap holds the band at "Needs Optimization" until either all G/R/V are present AND `dimensions_measured ≥ min_dimensions_for_full_band` (default 4). A 6-of-7 agent missing G is still capped.

**Precedence** (most specific wins): gate cap → completeness cap → band. A gated agent is held at 69 *and* flagged unsafe.

The two caps are distinguishable on the `Rating` via the `capped`, `cap_reason`, `unsafe`, and `gate_failures` fields. The widget renders all of them.

---

## Onboarding a new agent or source (three paths)

| Path | When to use | Work lands in |
|---|---|---|
| **1. Canonical POST** | The source already emits the full `AgentObservation` schema (or close to it) | Just `POST /ingest` with a JSON body. No code. |
| **2. YAML field-mapping** | The source emits arbitrary JSON, no SDK access, no time to write Python | Drop a `mapping_<name>.yaml` in `MAPPINGS_DIR` (default `./fixtures`). Auto-registers as `webhook:<name>`. See `fixtures/mapping_acme.yaml` for the full syntax. |
| **3. Custom `Adapter` or `SourceAdapter`** | The source needs Python (real client, format that YAML can't express) | `ingestion/generic/` for full observation, `ingestion/sources/<name>.py` for partial. Register in `ingestion/sources/__init__.py`'s `REAL_ADAPTERS`. Idempotent — `register_all()` is called from `api/bootstrap.py`. |

**Adapter shape**:
- `Adapter.to_observations(payload) → list[AgentObservation]` (used for complete observations; routed by `/ingest/{name}`).
- `SourceAdapter.to_partials(payload) → list[PartialObservation]` (used for one dimension at a time; routed by `/ingest/source/{name}`; the API merges latest-per-dimension per agent before scoring).

The engine math never changes. The point of the registry is that adding a new entry does not touch any other file.

---

## Settings / tunables (where they live)

Two places, both introspectable at runtime:

1. **Code defaults** — `contract/settings.py`. The `Settings` Pydantic model plus `DEFAULT_WEIGHTS`, `DEFAULT_Q_SUB_WEIGHTS`, `DEFAULT_GATE_THRESHOLDS`. `R_max` default is calibrated to **3.0** (changed from 10.0 in commit `b8ff21a`). Change defaults here only when the spec changes; per-deployment overrides go in the DB.
2. **Per-deployment overrides** — `GET /settings` reads, `PUT /settings` writes. Persisted in `SettingsRow`; the API hydrates `Settings` from the DB on every `score_and_persist`.

Keys the operator can change without redeploying: `weights` (P/Q/E/G/R/V/C, must sum to 1.0), `q_sub_weights` (accuracy/consistency/hallucination, must sum to 1.0), `gate_thresholds` (G/R/V floors), `r_max`, `human_cost_per_output`, `utilization`, `normalization_factor`, `min_dimensions_for_full_band`.

Per-agent **productivity baseline** lives separately in `AgentRow.baseline_human_output`. The first `POST /ingest?baseline=N` (or `dpi_ls.monitor(..., human_baseline=N)`) sets it; subsequent ingests update it only if `?baseline=` is passed again.

---

## The `dpi_ls` package (the user-facing 2-line surface)

`pip install git+https://github.com/phanindraintelligenzit-afk/widget.git` and then:

```python
import dpi_ls
collector = dpi_ls.monitor(my_agent, agent_id="my-agent", human_baseline=1)
# ... user's existing agent code, unchanged ...
```

`monitor()` does four things: starts the FastAPI dashboard in a background thread (idempotent — reuses a running server if one is already on the port), builds a `SignalCollector`, auto-detects the framework from the object's module name and installs the matching patcher, and registers an `atexit` finalizer that runs the LangGraph Q evaluator and POSTs the canonical `AgentObservation` to `/ingest`.

### `monitor()` escape hatches (for tests, CI, and debugging)

| Flag / env var | Default | Use case |
|---|---|---|
| `block=False` | `True` if attached to a TTY | CI / non-interactive runs — don't pause on exit |
| `post=False` | `True` | Tests / debugging — skip the `/ingest` POST (still accumulates signals) |
| `open_browser=True` | `False` | Pop the dashboard tab in a browser on script start |
| `DPI_LS_NO_BLOCK=1` | unset | Equivalent to `block=False` without changing code |
| `DPI_LS_OPEN_BROWSER=1` | unset | Equivalent to `open_browser=True` |
| `DPI_LS_DASHBOARD=0` | unset | Suppress "POST /ingest failed" log lines when no dashboard is running |
| `DPI_LS_OBS_PATH=/path.json` | `./dpi_ls_observation.json` | Where `dpi_ls.poster.write_local_copy()` writes the observation for offline ingest / debugging |
| `human_baseline=N` | DB value (100 on first run) | The P-dimension denominator — `1` for a single-run report agent, `100` for a batch of 100 tickets |

### Public surface (everything else is internal)

- `dpi_ls.monitor()` — the entry point
- `dpi_ls.SignalCollector` — exposed for tests and for custom framework patchers
- `dpi_ls.evaluate_quality(outputs)` — run the LangGraph Q evaluator on a list of agent prose outputs directly; returns `QResult(accuracy, consistency, hallucination_rate)`. Falls back to deterministic heuristics when the LLM is unreachable.

### Multi-agent / multi-framework in one process

`SignalCollector` is a process-wide singleton — calling `monitor()` twice overwrites it. To score several agents in one process (the orchestrator pattern in `examples/run_all.py`):

```python
from dpi_ls import _state
from dpi_ls.monitor import _finalize

dpi_ls.monitor(crew_a, agent_id="crew-a", human_baseline=1); crew_a.kickoff()
_finalize()                  # force the atexit handler now
_state.reset_for_tests()     # clear the singleton

dpi_ls.monitor(graph_b, agent_id="langgraph-b", human_baseline=1); graph_b.invoke({...})
_finalize()
```

Each `agent_id` lands as a separate row on the board. `_finalize` and `_state` are underscore-prefixed but stable; they're the only way to do batch scoring in one process.

### Heavy framework deps are optional for the server

`pyproject.toml` lists `pyautogen`, `crewai`, `llama-index`, `langgraph`, `langchain-aws`, `openai-agents`, `arize-otel` etc. — **all of these are patcher-side only**. The engine, the contract, the API, the store, and the widget are zero-dependency on agent frameworks. If you're only running the server (or writing a custom adapter), you can `pip install` the engine subset without them; framework patchers are lazy-imported, so missing packages simply disable the matching patcher.

## Test layout

- `tests/conftest.py` — per-test fresh in-memory SQLite, resets both adapter registries, points `MAPPINGS_DIR` at `fixtures/` so `mapping_acme.yaml` auto-registers. Use the `client` fixture for API tests; import the engine directly for engine tests.
- `tests/test_engine_reference.py` — **the four spec numbers**. If this file fails, the engine is broken. Run this first.
- `tests/test_engine_formulas.py` — edge cases for the 7 metric formulas and the gate/cap pipeline.
- `tests/test_engine_components.py` — band, gates, completeness individually.
- `tests/test_dpi_ls_*.py` — the `dpi_ls` package: collector, framework patchers, end-to-end monitor() → POST → score round-trip.
- `tests/test_api_*.py` — FastAPI routes; one file per concern (agents, ingest, settings, sources, sme_flow, sme_rating).
- `tests/test_{webhook,otel,partial_merge,mapping,...}.py` — adapter paths.
- `tests/test_{arize,aws_cost,bedrock,sap_hr,langgraph,audit_trail,bmc,servicenow,ray}.py` — per-adapter, with fixtures in `fixtures/source_<name>.json`.

**Useful invocations**:
```bash
uv run pytest tests/test_engine_reference.py -v     # the 4 spec numbers
uv run pytest tests/test_api_ingest.py -v          # ingest path round-trip
uv run pytest -k "gate" -v                          # all gate-related tests
uv run pytest -k "policy" -v                        # policy/governance scanner tests
uv run pytest tests/ --co -q                        # list test IDs only
uv run pytest tests/ -q --tb=short                  # short tracebacks on failure
```

The full suite is **302 tests, < 12 s** on a developer laptop.

**Governance testing notes**: Tests for the policy scanner in `dpi_ls/policy.py` gracefully skip optional engines if their dependencies are not installed. For instance, `test_presidio_*` tests skip if `presidio-analyzer` is not in the venv. To test all governance engines, run:
```bash
uv pip install presidio-analyzer detect-secrets chromadb sentence-transformers
uv run pytest -k "policy" -v
```

**Risk testing notes**: Lakera Guard is optional and paid. Tests for passive risk detection (exceptions, tool errors) run always. Tests that call the Lakera API will skip if `LAKERA_API_KEY` is missing (no charge incurred). To test with Lakera enabled:
```bash
export LAKERA_API_KEY=your_key_here  # or add to .env file
uv run pytest -k "risk" -v            # tests will call Lakera API if key is set
```
Without the key, passive risk tests still run and validate R-scoring on framework errors alone.

---

## Project state (where we are)

- **M0** Scaffold + `contract/` + `fixtures/` — done
- **M1** `engine/` pure scoring + reference tests — done
- **M2** `ingestion/` + `GenericWebhookAdapter` + OTel + YAML mapping — done
- **M3** `api/` + `store/` + score history — done
- **M4** `widget/` (vanilla web components, no framework) — done
- **M5** Real source adapters: `aws_cost`, `puvi_noise`, `arize`, `bedrock`, `sap_hr`, `audit_trail`, `ray`, `servicenow`, `bmc`, `jira`, `langgraph`, `langsmith`, `agentops`, `langfuse`, `braintrust`, `galileo`, `openllmetry`, `opik` — done. `stubs.py` now has `ALL_STUBS = ()` — there are no real stubs left.
- **M6** Conversational Q-capture (`engine/sme_flow.py` + `api/sme_orchestration.py`) — done.
- **M7 (current)** Enhanced governance detection: replaced regex-based scanner with multi-engine approach (Presidio NLP, detect-secrets, semantic RAG, OPA Rego rules). Added compliance rule sets (SOX/GDPR/SOC2, HIPAA, PCI-DSS, ISO27001) and governance examples.

Current work is post-M6 hardening: recent commits integrate OPA policy engine, NLP-based PII detection via Presidio, and semantic policy matching via Chroma embeddings. The demo target — *score one real agent with full governance scanning* — is reachable via `examples/test_governance_agent.py`.

**`dpi_ls` package is a separate concern from the server.** They share `contract/` (the observation schema is the wire format) but the package never imports from `engine/`, `store/`, or `api/` — it talks to the server over HTTP via `dpi_ls/poster.py`.

---

## Conventions / non-negotiables

- **Mock-first.** Every adapter runs against `fixtures/` before any real credential exists. Source adapters in `ingestion/sources/` accept the JSON shape those systems produce; the live HTTP fetch is intentionally not wired up yet.
- **Engine is pure and fully unit-tested.** No network/DB calls in `engine/`. The four reference outputs are the spec — don't "fix" them by relaxing the test.
- **Typed everywhere** (Pydantic v2 + type hints).
- **Real math only.** No fudged scores, no fabricated agent data in demos — synthetic fixtures are clearly labelled as fixtures (`_label` field is stripped by `scripts/demo_seed.sh` before posting).
- **Secrets via env vars** (`.env.example` is the template), never hardcoded. The venv is at `.venv/` and is `.gitignore`d.
- **All tunables live in settings**, not in code. See "Settings / tunables" above.

---

## Governance detection (G dimension) — multi-engine scanning

The G-dimension policy scanner in `dpi_ls/policy.py` uses four detection engines (all optional; gracefully degrade if not installed):

1. **Presidio (NLP-based PII detection)** — Installs: `pip install presidio-analyzer`. Detects credit cards, SSNs, emails, phone numbers, auth tokens, and more by entity type. High-confidence threshold = 0.6 to reduce false positives. Replaces legacy regex-based scanning.

2. **detect-secrets (credential scanning)** — Installs: `pip install detect-secrets`. Detects AWS keys, Slack tokens, private keys, basic auth, JWT tokens, and other secrets. Plugin-based; enabled plugins are AWS, Slack, PrivateKey, BasicAuth, JWT.

3. **Semantic RAG (Chroma + embeddings)** — Installs: `pip install chromadb sentence-transformers`. Uses vector similarity to detect policy violations by matching agent outputs against a semantic embedding database of known violations. Threshold = 0.45. Useful for domain-specific or custom policies. Maintained in `examples/governance_dimension/embedding/chroma.sqlite3`.

4. **OPA (Open Policy Agent)** — Installs: `opa` CLI tool or `pip install pydantic-opa`. Runs deterministic Rego rules against agent actions. Rules live in `examples/governance_dimension/policies/`. Covers enterprise compliance (SOX, GDPR, SOC2), cloud infrastructure, healthcare (HIPAA), PCI-DSS, ISO27001, and custom policies.

All engines are independent; violations from any engine count toward the G-score floor. The collector in `monitor()` calls `scan_policy_violations()` on every agent action; if any engine detects a violation, the action is flagged.

**Useful governance examples**:
- `examples/test_governance_agent.py` — End-to-end agent with OPA rule enforcement.
- `examples/governance_dimension/yaml_governance_guard.py` — YAML-based policy definitions.
- `examples/governance_dimension/presidio_governance_guard.py` — Presidio PII detection demo.
- `examples/governance_dimension/detect_secrets_governance_guard.py` — Credential detection demo.
- `examples/governance_dimension/policies/*.yaml` — Pre-built compliance rule sets.

---

## Quality evaluation (Q dimension) — LangGraph + fallback heuristics

The Q-dimension evaluator in `dpi_ls/evaluator.py` scores agent prose outputs on three sub-metrics:

**LangGraph Evaluator (primary)**: Uses a three-node state machine running on AWS Bedrock (model ID from `BEDROCK_MODEL_ID` or `MODEL_NAME` env vars):
- **Accuracy** (0.7 weight) — Does the agent's analysis accurately reflect the retrieved/tool data?
- **Consistency** (0.2 weight) — Is the output logically coherent, free of contradictions?
- **Hallucination Rate** (0.1 weight) — What fraction of specific factual claims lack grounding in the source data?

Each node prompts the LLM to score 0–1, parsed strictly. Source data (tool results, retrieved docs) is included when available to ground hallucination scoring.

**Fallback Heuristics** (`dpi_ls/heuristics.py`): If Bedrock is unavailable (no credentials, misconfigured, or API fails), the evaluator transparently falls back to deterministic rules:
- Accuracy penalizes error-shaped or very-short/very-long outputs; bonuses reasonable length (50–5000 chars)
- Consistency measures variance between successive outputs
- Hallucination estimates based on concrete tokens (numbers, UUIDs, file paths, IDs)

The heuristics are rough but prevent silent Q drops during demo/testing. Real Q signal should come from the LangGraph evaluator or the SME conversational flow.

---

## Risk detection (R dimension) — Lakera Guard + incident tracking

The R-dimension risk scanner in `dpi_ls/risk.py` can use **Lakera Guard API** to detect adversarial threats in agent inputs and outputs. **Note: Lakera Guard is a paid commercial service** (usage-based pricing; see https://lakera.ai for current rates). For cost-conscious deployments, risk detection can also rely on passive signals (framework exceptions, tool errors) without any external API cost.

**Lakera Guard coverage** (when enabled):
- **Prompt Injection** — Detects attempts to override system instructions or manipulate agent behavior.
- **Jailbreaks** — Identifies techniques to bypass safety constraints.
- **Toxicity** — Flags offensive, harmful, or abusive language.
- **PII Detection** — Catches sensitive data like credit cards, SSNs, credentials in outputs.

The API returns confidence levels (l1 = most confident, l5 = least confident), mapped to severity weights (1.0 to 0.2) that feed into the R metric formula.

**Configuration**:
- **Enable**: Set `LAKERA_API_KEY` env var; collector will call the API on every agent input/output
- **Disable**: Omit `LAKERA_API_KEY`; system falls back to passive risk detection (exceptions, tool errors only)
- Gracefully handles API unavailability (timeouts, rate limits, service errors) — returns empty incidents without crashing

**How it integrates**: The collector in `dpi_ls/monitor()` runs Lakera scans **asynchronously** on:
- **Inputs** (user prompts) — catches adversarial prompts before the agent sees them.
- **Outputs** (agent responses) — catches PII leaks or toxic outputs after generation.

When Lakera detects a threat, it's recorded as an incident with `source=lakera:{detector_type}`. All incidents (Lakera + framework exceptions + tool errors) contribute to the R-score via the formula:
```
R = 1 − min(1, Σ(frequency × severity_weight) / R_max)
```

Where `R_max = 3.0` (calibrated default; tunable via `/settings` API).

**Cost considerations**:
- **Production**: Budget per-call Lakera pricing (typically $0.005–$0.05 per scan depending on tier and volume).
- **Demo/CI**: Omit `LAKERA_API_KEY` to avoid charges; agents will be scored on passive signals only (R will be 1.0 unless there are framework errors).
- **Hybrid**: Use Lakera only for production deployments; skip for test environments.

**Passive risk detection** (no cost, always enabled):
- Framework exceptions recorded as `source=framework:error` incidents
- Tool call failures recorded as `source=tool:error` incidents
- These alone can floor the R-score if severe enough per `R_max` tuning

**Useful risk examples**:
- `examples/test_risk_agent.py` — End-to-end agent with intentionally risky tool use (deletion, wire transfers, admin grants). Demonstrates Lakera Guard detecting both prompt-injection inputs and tool-action risks (set `LAKERA_API_KEY` to see Lakera detections; omit to see passive incidents).
- `examples/risk_dimension/lakera_risk_guard.py` — Direct Lakera Guard API integration demo.

---

## Execution detection (E dimension) — tool success tracking

The E-dimension metric tracks tool execution success: `E = successful_executions / total_attempts`. The collector in `dpi_ls/collector.py` auto-detects LLM tool calls via framework patchers:

**How it works**:
- Each framework patcher (`langchain.py`, `langgraph.py`, `openai_agents.py`, etc.) intercepts tool invocations
- On call, `collector.attempts += 1`
- On success, `collector.successful += 1`
- On error, `collector.record_error(exc)` (recorded as an R-dimension incident, not an E failure)
- Final metric: `E = successful / attempts`, clamped to [0, 1]

**Edge case**: Tool calls that return structured data (e.g. API responses) without text output still count as successful in E. The output text is captured separately for V (validation) and Q (quality) evaluation.

**Framework coverage**: All supported frameworks (LangChain, LangGraph, CrewAI, Autogen, LlamaIndex, OpenAI Agents, raw OpenAI/Anthropic) auto-increment attempts/successful via their respective patcher.

---

## Validation detection (V dimension) — structured output patterns

The V-dimension metric detects whether agent outputs are *properly formatted* and *validated*: `V = validated_components / total_required`. The collector in `dpi_ls/collector.py` scans each output text for structured patterns:

**Patterns detected** (in `_VALIDATION_PATTERNS` and `_VALIDATION_SEARCH_PATTERNS`):
- **JSON/YAML/CSV blocks** — Fenced code blocks (` ``` ` delimiters) containing structured data
- **XML/HTML tags** — Semantic wrappers like `<answer>`, `<result>`, `<response>`
- **Markdown tables** — Pipe-delimited columns (`| Col1 | Col2 |`)
- **Markdown headers** — Structured sections with `## Title` or `### Subtitle`

An output is considered "structured" if it matches ANY of these patterns. The collector counts:
- **validated_components** — number of outputs with detected structure
- **total_required** — total number of outputs captured

V is then clamped to [0, 1]. A 100%-structured agent (all outputs JSON, markdown tables, or tagged) scores `V=1.0`. A prose-only agent with no structure scores `V=0.0`.

**Use case**: V protects against agents that produce correct *content* but in unstructured formats that are hard for downstream consumers to parse. Combined with Q, it ensures both *quality of reasoning* and *usability of output format*.

---

## Cost calculation (C dimension) — dynamic AWS Bedrock pricing

The C-dimension cost metric tracks AI cost efficiency: `C = min(1, human_cost_per_output / AI_cost_per_output) × utilization`.

**Dynamic Pricing (`dpi_ls/cost_calculator.py`)**:
The `BedrockDynamicCostCalculator` fetches live Bedrock model pricing from AWS Pricing API at runtime — no hardcoded model IDs or fallback prices:
- Lists all available foundation models via `bedrock.list_foundation_models()`
- Queries AWS Pricing API for each model's input and output pricing (per 1M tokens)
- Matches catalog entries by model ID, model name, or usage type
- Returns `(input_price_per_1M, output_price_per_1M)` tuples

**Cost calculation**:
```
model_cost_usd = (input_tokens / 1_000_000) × input_rate + (output_tokens / 1_000_000) × output_rate
```

Token counts come from LLM response metadata (`usage.prompt_tokens` / `usage.completion_tokens`). All framework patchers extract tokens and pass them to `collector.record_llm_call(..., tokens_in=N, tokens_out=M)`.

**Human cost baseline**: Operators set `human_cost_per_output` (e.g., `$0.50` for a support ticket resolved by a human) via the `/settings` API. The C metric then expresses: "For every $1 we pay humans, we pay $X to the AI model." Lower X = better efficiency.

**Utilization factor**: The C formula also includes a `utilization` multiplier (default 1.0, tunable) to account for idle time or partial use of resources.

---

## Observability platform integrations (Arize, LangFuse, etc.)

The system integrates with external observability platforms as **source adapters** (`ingestion/sources/`), allowing those platforms' signals to feed into DPI-LS scoring:

**Arize** (`ingestion/sources/arize.py` + `examples/arize_governance_violator.py`):
- Consumes Arize model monitoring data: drift detection, embedding L2 divergence, custom monitors
- Monitor breaches → **G (Governance)** dimension violations
- Arize quality scores (accuracy, consistency, hallucination) → **Q (Quality)** dimension
- Routes via `POST /ingest/source/arize` with agent list + breaches per monitoring period

**Framework instrumentation examples**:
- `examples/arize_governance_violator.py` — Governance violator scenarios instrumented with Arize OTel, traces sent to Arize platform
- `examples/execution_dimension/test_langfuse.py` — Orchestrator agent instrumented with LangFuse tracing (execution/tool call tracking)
- `examples/execution_dimension/test_traceloop.py` — Orchestrator agent with Traceloop instrumentation

These are **optional parallel signals**: an agent can be scored by `dpi_ls.monitor()` alone, or have external platform data merged in via source adapters, or both (dpi_ls signals + Arize breaches + LangFuse traces all combined).

---

## Multi-agent orchestration patterns

**Single-file orchestrator** (`examples/orchestrator_agent.py`): A 50KB+ LangGraph state machine that combines generator, executor, and orchestrator phases into one self-healing AWS automation pipeline. Features:
- Checkpointer fallback: Postgres → SQLite → in-memory
- Interruption support: `langgraph.types.interrupt()` for human-in-the-loop
- Retry loop with feedback: up to 5 iterations, reads existing state, learns from failures
- File and command execution: Uses `FileManagementToolkit` and subprocess isolation

**Multi-agent pattern** (`examples/run_all.py`): How to score multiple agents in a single process using the `_finalize()` / `_state.reset_for_tests()` escape hatch (since `SignalCollector` is a process-wide singleton).

---

## Common gotchas

- **`Q = None` is intentional**, not a bug. It means "needs conversational/SME input". The composite redistributes weight off None metrics, and the completeness cap holds the band at "Needs Optimization" until Q arrives. Don't substitute 0.
- **A C-only agent will *raw-score* near 100** (the composite divides by the redistributed weight, giving `C^(1.0) × 100`). That's correct — the completeness cap is what holds the band. The dashboard will show a high raw score with `coverage_capped=true` and `cap_reason="low-coverage ..."`.
- **`human_baseline` is per-agent and stored in the DB**, not a global setting. The first ingest sets it; subsequent ingests update it only when the request includes `?baseline=N`.
- **Adapter names must be unique across both registries** (`ingestion.registry` for full adapters, `ingestion.sources.registry` for source adapters). The `register_all()` function in `ingestion/sources/__init__.py` is idempotent; `ingestion.sources.register_all()` is called by `api/bootstrap.py`.
- **The widget bundle is served as a static file** at `/widget/dpi-ls.js` and `/widget/demo.html`. The FastAPI app mounts `widget/` as a static dir; the `GET /` route redirects to `widget/demo.html`. No build step — the JS file is what you ship.
- **CORS is `*` by default** for the demo. Set `WIDGET_ALLOWED_ORIGINS=https://a.com,https://b.com` in production.
- **Two adapter families route through different endpoints**: `/ingest/{adapter_name}` for full `Adapter`s (resolves the payload to `AgentObservation` server-side), `/ingest/source/{name}` for `SourceAdapter`s (resolves to `PartialObservation` and merges with prior partials for the same agent).

---

## Build sequence — do ONE milestone at a time, run tests, STOP, show

The spec's build sequence (M0 → M6) is complete. Any new work is post-M6 — likely a new source adapter (use the "Onboarding" table above), a new framework patcher in `dpi_ls/frameworks/`, or a new SME flow step. None of those touch `engine/`.

---

## Out of scope (parked)

Agent marketplace, subscription/billing, multi-tenant onboarding, the full "typical day in the life" workflow. Demo target = **score one real agent, live.** Live HTTP fetch for source adapters (boto3, ServiceNow REST, Jira REST) is parked at the *next* milestone after the demo is solid.

---

## Root-level scratch files (do NOT treat as product code)

A handful of files at the repo root are **dev scratch, not part of the product**:

- `how_to_run.txt` — 5-line cheatsheet from an earlier session. Redundant with the "See the demo in 3 commands" block above; leave or delete, don't refactor.
- `changes.txt` — stale project-management notes from an earlier session (refers to "121 tests" — we're at 302; refers to an old M0–M5 plan). Not authoritative; the real spec is this file + `README.md`.
- `check_db.py` — one-off SQLite inspector script for poking at `dpi_ls.db` from the command line. Not a test, not part of the API. Run with `.venv/Scripts/python.exe check_db.py` if you need to eyeball a row.
- `cost.py` — a stray AWS Cost Explorer boto3 client that does **not** import from this project at all. Old exploration code. Don't conflate with `ingestion/sources/aws_cost.py`.

A future Claude asked to "tidy the root" should leave these alone unless explicitly directed. The product surface is everything in `contract/`, `engine/`, `ingestion/`, `api/`, `store/`, `dpi_ls/`, `widget/`, `tests/`, `examples/`, `fixtures/`, and `scripts/`.

**Non-product directories**:
- `documents/` — LaTeX source (`.tex`) and PDF render of the 7-dimension formulas (cost, execution, governance, productivity, quality, risk, validation). Reference material; the source of truth is `engine/metrics.py` and `contract/models.py`.
- `resourceDocuments/` — MS Word `.docx` files with detection strategy and resource lists for E, G, and R dimensions. Development reference; not packaged with the product.
- `images/` — Project screenshots and diagrams. Documentation assets; not part of the API or package.
