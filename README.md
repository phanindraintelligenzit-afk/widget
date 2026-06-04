# DPI-LS — Digital FTE Performance Index, engine + embeddable widget

Score any AI agent in real time on a 0–100 index across 7 dimensions, with
hard compliance gates. Includes a framework-free web component you can drop
into any host page to show the live rating.

The pitch this serves: *"hand it an agent — I'll score it live."*

The design rationale, hard requirements, and the full scoring spec live in
[CLAUDE.md](./CLAUDE.md). This README is the runbook.

---

## Quick start

Requires Python 3.11+, `pip`, and (optionally) `jq` for the seed script.

```bash
git clone <repo-url> dpi-ls
cd dpi-ls

# 1. Install the package and its runtime deps
pip install -e .

# 2. Boot the API. SQLite is fine for the demo; swap DATABASE_URL for Postgres
#    in prod. MAPPINGS_DIR auto-registers any mapping_*.yaml as a webhook adapter.
DATABASE_URL="sqlite:///./dpi_ls.db" \
MAPPINGS_DIR=./fixtures \
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
```

In a second terminal, seed the fixtures so the board has data:

```bash
./scripts/demo_seed.sh
```

Open **http://localhost:8000/** in a browser — it redirects to the live demo at
`/widget/demo.html`. The board polls every 3 seconds.

---

## What you'll see

The demo page shows four embeddable components, all backed by the same API:

| Component | What it does |
|---|---|
| `<dpi-ls-board>` | Live board polling `/ratings`. One card per agent: score, band pill, Unsafe banner when a gate has fired. |
| `<dpi-ls-agent agent-id="…">` | Per-agent card polling `/agents/{id}/score`. Shows all 7 sub-metrics; "SME" for any metric still deferred. |
| `<dpi-ls-sme-prompt agent-id="…">` | Conversational 3-question quality capture (accuracy → consistency → hallucination → review). |
| `<dpi-ls-settings>` | Tunables form: weights, Q sub-weights, gate thresholds, R_max, utilization, human $/output. Validates that composite weights sum to 1.0 before save. |

### Demo path (90 seconds, after seeding)

1. **Board** shows 6 agents. The Procurement Agent (`agent-unsafe-003`) is in a red
   Needs-Optimization band: `G < 0.60` triggered the compliance gate, capping the
   raw score (79.6) to 69 and flagging Unsafe.
2. **Multi-source agent** (`agent-multi-001`) was assembled from 5 independent
   systems — AWS Cost feeds C, Puvi/Arize feed G + Q, ServiceNow/Jira feed R.
   The per-agent card shows "Pending SME input: P, E, V" because no source in
   this set speaks to those dimensions yet.
3. **Click "Start review"** on the SME widget. Enter 93, 91, 5, yes.
   Q lights up, the agent's score updates within the next poll cycle.
4. **Settings** — tighten the G gate threshold to e.g. 1.01, hit Save.
   Re-POST `fixtures/obs_strong.json` to `/ingest` — the previously Exceptional
   agent is now flagged Unsafe (the change took effect on the next ingest).

---

## The DPI-LS score

Each sub-metric normalises to [0, 1]:

| Metric | Definition |
|---|---|
| **P** — Productivity | `min(1, AI_outputs / human_baseline)` |
| **Q** — Quality | `0.70·Accuracy + 0.20·Consistency + 0.10·(1 − Hallucination)` |
| **E** — Execution | `successful_executions / attempts` |
| **G** — Governance | `1 − (policy_violations / total_actions)` |
| **R** — Risk        | `1 − min(1, Σ(freq × severity) / R_max)` |
| **V** — Validation | `validated_components / required` |
| **C** — Cost | `min(1, human_cost / AI_cost) × utilization` |

Composite — weighted geometric mean:

```
DPI-LS = 100 · ( P^.15 · Q^.20 · E^.15 · G^.20 · R^.15 · V^.10 · C^.05 )
```

**Hard compliance gates.** If `G < 0.60` OR `R < 0.50` OR `V < 0.60`, the score
is capped at 69 (top of *Needs Optimization*) and flagged Unsafe — regardless
of the raw composite.

**Bands.** `85–100 Exceptional · 70–84 Strong · 50–69 Needs Optimization · <50 Underperforming/Unsafe`.

**Reference outputs** (asserted in `tests/test_engine_reference.py`):

| Input | Expected score |
|---|---|
| All metrics 0.85 | 85 |
| All metrics 0.92 | 92 |
| All metrics 0.55 | 55 |
| All 0.85, but G = 0.25 | raw 67, capped to 67, flagged Unsafe |

---

## API surface

All endpoints are JSON. CORS is `*` by default for the demo —
set `WIDGET_ALLOWED_ORIGINS=https://a.com,https://b.com` to tighten.

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness |
| GET | `/` | Redirects to `/widget/demo.html` |
| GET | `/adapters` | Registered full-observation adapters (`otel`, `webhook:acme`, …) |
| GET | `/sources` | Registered source adapters (`aws_cost`, `puvi_noise`, `arize`, `servicenow`, `jira`, + 5 stubs) |
| POST | `/ingest` | Body: a canonical `AgentObservation` |
| POST | `/ingest/{adapter_name}` | Body: whatever that adapter takes (e.g. OTel spans, or Acme's payload through `webhook:acme`) |
| POST | `/ingest/source/{name}` | Body: that source's payload. The API stores partials, re-merges per agent, re-scores. |
| GET | `/ratings` | Board view — one row per agent, latest score |
| GET | `/agents` | List all known agents |
| GET | `/agents/{id}/score` | Latest `Rating` (score, band, gate failures, all 7 metrics, `missing`) |
| GET | `/agents/{id}/history` | Newest-first score history |
| GET / PUT | `/settings` | Get/replace tunables (`Settings`) |
| POST | `/sme-flow/start` | Begin a conversational quality capture. Body: `{agent_id, submitted_by}` |
| POST | `/sme-flow/{session_id}/respond` | Body: `{response}`. Returns the next prompt and (on commit) the new Rating. |
| POST | `/agents/{id}/sme-rating` | Direct SME rating capture (audit-only, no conversation) |
| GET | `/widget/dpi-ls.js`, `/widget/demo.html` | The static widget bundle |

OpenAPI / Swagger UI: **http://localhost:8000/docs** when the server is up.

---

## Onboarding a new agent or source

This is the whole point of the architecture. **Never edit `engine/`.**
Two paths, depending on what you're integrating:

### Path 1 — the source emits a complete observation

If your agent runtime (or an aggregator like an OTel collector) can produce
the full canonical `AgentObservation`, just post it. No code needed:

```bash
curl -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' -d @observation.json
```

If it emits a non-canonical JSON shape, write a YAML field mapping and drop it
into `MAPPINGS_DIR`. The bootstrap auto-registers it as `webhook:<source>` and
exposes `/ingest/webhook:<source>`. See `fixtures/mapping_acme.yaml` for the
full mapping syntax (dot/bracket paths, `_each` for iteration, `_optional` for
nullable groups).

### Path 2 — the source only knows one dimension

Cost data comes from AWS, governance from Arize, incidents from ServiceNow.
Write a small `SourceAdapter` that returns `list[PartialObservation]` — each
carrying only the dimension(s) that source observes. The API merges
latest-per-dimension across all partials before scoring, so the engine never
sees a "missing C means C is zero" situation.

The five real source adapters under `ingestion/sources/` are the template;
each is under 80 lines.

---

## Configuration

Everything tunable is an env var:

| Env var | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./dpi_ls.db` | SQLAlchemy URL. Use `postgresql+psycopg2://…` in prod. |
| `MAPPINGS_DIR` | (unset) | Folder scanned at startup for `mapping_*.yaml`. Each is registered as `webhook:<source>`. |
| `WIDGET_ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowlist. |

Per-deployment tunables (composite weights, gate thresholds, R_max, etc.)
live in the database `settings` table, fetched / written via
`GET /settings` and `PUT /settings`. There is one Settings row.

---

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

121 tests, < 2 seconds. The four spec reference cases are in
`tests/test_engine_reference.py`. If any of those break, the engine is wrong.

---

## Repo layout

```
contract/      Pydantic models — the canonical AgentObservation + PartialObservation
engine/        PURE scoring. No I/O. metrics, score, gates, bands, SME state machine
ingestion/
  generic/     GenericWebhookAdapter (YAML mapping) + OTelAdapter (universal fallback)
  sources/     aws_cost, puvi_noise, arize, servicenow, jira + 5 stubs
api/           FastAPI app, routes, orchestration, bootstrap
store/         SQLAlchemy models + repo (agents, observations, partials, score_history,
               settings, sme_ratings, sme_flow_sessions)
widget/        dpi-ls.js (vanilla web components) + demo.html
fixtures/      Synthetic payloads — clearly _label-tagged — used by tests and the demo
tests/         121 tests, including the four DPI-LS reference outputs
scripts/       demo_seed.sh
```

---

## What's intentionally not done

This is a working demo, not a production deployment. The omissions are the
ones called out in [CLAUDE.md](./CLAUDE.md) as parked, plus the obvious
prod hardening:

- **No auth.** Anyone who can reach the API can POST observations or PUT settings.
- **Live source connectors** (boto3, ServiceNow REST, Jira REST) aren't wired.
  The source adapters accept the JSON shapes those systems would produce; the
  HTTP fetch layer is the next milestone for any one of them.
- **`langgraph`, `bedrock`, `ray`, `bmc`, `sap_hr`** source adapters are stubs
  that register and return `[]`. The interface is in place; the body is the
  on-ramp.
- No Dockerfile, no migrations framework (Alembic), no rate limiting,
  no observability/metrics export.
- Agent marketplace, multi-tenant onboarding, billing — parked per the spec.

The pieces that *are* done — the engine, the contract, the ingestion pattern,
the widget — were built to make any of the above incremental: a real AWS
adapter is "fill in the fetch step on `AwsCostAdapter`," not a rewrite.
