# DPI-LS — Engine + Embeddable Appraisal Widget

## What we're building
A service that scores **any AI agent** in real time on the **Digital FTE Performance Index (DPI-LS, 0–100)**, plus an **embeddable widget** that shows the live score. Hand it an agent → live rating across 7 dimensions, compliance-gated. The pitch this serves: *"give me an agent, I'll score it live."*

Solo build, driven via Claude Code. Optimize for a working demo, not completeness.

---

## THE ONE HARD REQUIREMENT: agent-agnostic
The engine must **not know or care how an agent is built** (LangGraph, Bedrock Agents, CrewAI, in-house, anything). It connects to "any agent" through one decoupling pattern — internalize this before writing code:

1. **Canonical Telemetry Contract** — a single normalized schema (Pydantic). The engine computes the 7 metrics *only* from this object.
2. **Adapters** — thin plugins that translate one source (an agent runtime OR an observability/ITSM tool) into the canonical contract. Swappable, discovered via a registry.
3. **Universal fallback** — a `GenericWebhookAdapter` + OpenTelemetry ingestion driven by a **declarative YAML field-mapping**. Any agent that can POST JSON or emit OTel spans is supported with **zero custom code**. Framework-specific adapters are optimizations layered on top.

**Hard rules:**
- The engine core depends **only** on the contract. Never `import` an agent framework into `engine/`.
- Onboarding a new agent = a new adapter **or** a new YAML mapping. Never an engine change.

---

## Architecture
```
dpi-ls/
  contract/      # Pydantic models — the canonical AgentObservation schema (BUILD FIRST)
  engine/        # PURE scoring. No I/O. metrics.py, score.py, gates.py, bands.py
  ingestion/     # adapter base class + registry
    generic/     #   GenericWebhookAdapter, OTelAdapter, yaml field-mapping (the universal path)
    sources/     #   stub adapters: langgraph, bedrock, puvi_noise, arize, ray,
                 #   servicenow, jira, bmc, aws_cost, sap_hr  — each with fixtures
  api/           # FastAPI: /ingest, /agents, /agents/{id}/score, /settings, /ratings
  store/         # Postgres (SQLAlchemy): observations, score_history, settings, ratings
  widget/        # embeddable web component <dpi-ls-board> / <dpi-ls-agent agent-id="...">
  fixtures/      # sample observations per source for mock-first dev + tests
  tests/
  CLAUDE.md
```

---

## Canonical contract (build this FIRST, in `contract/`)
A normalized snapshot of one agent over a period. Fields may be null → engine treats null as "needs conversational/settings input," not zero.
```python
class TaskStats(BaseModel):
    assigned: int; completed: int; failed: int
    pending_approval: int = 0; blocked_no_access: int = 0

class AgentObservation(BaseModel):
    agent_id: str; agent_name: str; period_start: datetime; period_end: datetime
    tasks: TaskStats
    executions: dict          # {attempts, successful}
    policy: dict              # {total_actions, violations: [{rule, when}]}
    incidents: list           # [{severity_weight, frequency, source}]
    quality: dict | None      # {accuracy, consistency, hallucination_rate} — may be null
    validation: dict          # {required_components, validated_components, audit_ready}
    cost: dict                # {ai_cost_per_output, tokens, cloud_cost, systems_accessed}
    source: str               # which adapter produced this
```
Every adapter's only job is to return one (or many) `AgentObservation`. The engine consumes nothing else.

---

## Scoring spec (exact — match precisely, tests must assert it)
Each sub-metric normalizes to **[0,1]**:
- `P = min(1, AI_output_per_period / human_baseline)`              (baseline from settings)
- `Q = 0.7·Accuracy + 0.2·Consistency + 0.1·(1 − Hallucination)`   (inputs 0–1; null → conversational)
- `E = successful_executions / total_attempts`
- `G = 1 − (policy_violations / total_actions)`
- `R = 1 − min(1, Σ(freq × severity) / R_max)`                     (R_max from settings)
- `V = validated_components / total_required`
- `C = min(1, human_cost_per_output / AI_cost_per_output) × utilization`

Composite — **weighted geometric mean** (one model, not a weighted sum):
```
DPI-LS = 100 × ( P^.15 · Q^.20 · E^.15 · G^.20 · R^.15 · V^.10 · C^.05 )
```
Compliance gates (hard floors): if `G < 0.60` OR `R < 0.50` OR `V < 0.60` → cap rating at "Needs Optimization" and flag Unsafe, regardless of score.

Bands: `85–100 Exceptional · 70–84 Strong · 50–69 Needs Optimization · <50 Underperforming/Unsafe`.

**Unit tests must assert these reference outputs:**
- all metrics .85 → **85**
- all .92 → **92**
- all .55 → **55**
- strong agent but G=.25 → raw **67**, gate fires, flagged Unsafe

---

## Stack
Python 3.12 · FastAPI · Pydantic v2 · Postgres (SQLAlchemy) · pytest. Widget: a framework-free **web component** (one `<script>` tag, drops into any host page). LangGraph only if/when we add the conversational-rating flow — not in the core. No low-code, no no-code.

---

## Conventions / non-negotiables
- **Mock-first.** Every adapter runs against `fixtures/` before any real credential exists. Never block the build on ServiceNow/Puvi/AWS access.
- **Engine is pure and fully unit-tested.** No network/DB calls in `engine/`. Tests assert the reference scores above.
- **Typed everywhere** (Pydantic + type hints).
- **Real math only.** No fudged scores, no fabricated agent data in demos — synthetic fixtures are clearly labelled as fixtures.
- Secrets via env vars, never hardcoded.
- All tunables (weights, `R_max`, gate thresholds, Q sub-weights, human cost/hr, utilization, per-agent baseline) live in **settings**, not in code.

---

## Build sequence — do ONE milestone, run tests, STOP, show me
Do not run ahead. After each milestone: run the test suite, summarize what changed, list what's next, and wait.

- **M0** Scaffold the repo per the tree above. Implement the `contract/` models + `fixtures/` (2–3 sample observations).
- **M1** `engine/` — metrics + geometric-mean score + gates + bands, with pytest tests asserting the four reference outputs. Pure, no I/O.
- **M2** `ingestion/` — adapter base class + registry + `GenericWebhookAdapter` + OTel ingest + the declarative YAML field-mapping. Push a fixture through to a computed score end-to-end.
- **M3** `api/` + `store/` — FastAPI endpoints + Postgres persistence + score history.
- **M4** `widget/` — embeddable web component: live board + per-agent card, polling the API. This is the demo surface.
- **M5** Real adapters that tell the story: `aws_cost` (C), `puvi_noise`/`arize` (G), `servicenow`/`jira` (R) — same interface. Stub the rest.
- **M6** Conversational rating capture (SME/QA → Q) + settings UI polish.

**Demo path priority if time is short:** M0 → M1 → M2 → M4 (with fixtures) → one real adapter (AWS cost). That's enough to score one real agent live. Everything else is incremental.

---

## Out of scope (parked)
Agent marketplace, subscription/billing, multi-tenant onboarding, the full "typical day in the life" workflow. Demo target = **score one real agent, live.**
