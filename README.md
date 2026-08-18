# DPI-LS — Digital FTE Performance Index for Life Sciences

> **A comprehensive report card for your AI Digital Workers — scoring them on a 0 to 100 scale across 7 performance dimensions, with built-in safety gates and a live dashboard.**

---

## What is DPI-LS?

When companies deploy AI to handle important work — like processing invoices, analyzing medical documents, or monitoring cloud costs — they need to know if the AI is doing a good job, working safely, and actually saving money.

**DPI-LS answers that question.** Instead of just hoping the AI works, DPI-LS automatically measures 7 critical performance areas and gives you a single, easy-to-understand score out of 100. It combines hard data from the AI's operations with subjective feedback from human managers to ensure the AI is truly adding value.

**We measure Trust, not just Productivity.** By bridging HR, Business, and Compliance, DPI-LS helps organizations manage AI as a workforce — with full lifecycle governance and accountability.

---

## The 7 Performance Dimensions

Every AI agent is evaluated across these 7 areas:

| Dimension | What It Measures | In Simple Terms |
|-----------|-----------------|-----------------|
| **P** — Productivity | How much work the AI completes compared to a human | "Is the AI faster than a person?" |
| **Q** — Quality | Accuracy, consistency, and hallucination rate of AI outputs | "Is the AI giving correct answers?" |
| **E** — Execution | Success rate of all AI tasks and tool calls | "Is the AI completing tasks without errors?" |
| **G** — Governance | Policy compliance — PII leaks, unauthorized access, secrets exposure | "Is the AI following the rules?" |
| **R** — Risk | Frequency and severity of incidents and exceptions | "Is the AI causing any problems?" |
| **V** — Validation | Whether outputs are properly structured (JSON, Markdown, tables) | "Is the AI producing well-formatted results?" |
| **C** — Cost | AI cost per output compared to human cost per output | "Is the AI saving us money?" |

### How the Final Score Works

The 7 dimensions are combined into a single weighted score out of 100:

- **85–100** → Exceptional
- **70–84** → Strong
- **50–69** → Needs Optimization
- **Below 50** → Underperforming

### Safety Gates

If the AI fails on Governance (G), Risk (R), or Validation (V), the system automatically caps the score and flags the agent as **Unsafe** — no matter how well it performs in other areas. A single PII leak will trigger this safety gate.

---

## How DPI-LS Works — The 6-Step Workflow

### Step 1: Agent Onboarding

Before tracking an AI's performance, you register it in the system. You provide:
- A unique Agent ID and description
- The agent's business role (e.g., Finance, Healthcare, IT)
- The environment (Production, Staging, etc.)
- Human owners: a Manager, Business Owner, and Technical Owner

This ensures every AI has clear human accountability and is never running without supervision.

**URL:** `http://localhost:8000/widget/onboarding.html`

---

### Step 2: KRA Configuration

KRA stands for **Key Result Area**. Not all AI agents have the same goals, so in this step you define:
- **What success looks like** — a target value (e.g., 99.5% accuracy)
- **How important it is** — a weight between 0 and 1 (e.g., 0.85 means 85% importance)

This tells the scoring engine which metrics matter most for this specific agent.

**URL:** `http://localhost:8000/widget/kra.html`

---

### Step 3: Static Data Configuration

To know if an AI is truly saving time and money, we need to compare it against how a human would do the same job. In this step you set:
- **Human Baseline** — how many tasks a human completes per period (e.g., if a human processes 10 invoices per hour, set baseline to 10)
- **Normalization Factor** — any adjustment factors for fair comparison

When the AI processes 20 invoices in the same time, the system mathematically proves it is 2x more productive than the human.

**URL:** `http://localhost:8000/widget/agent-config.html`

---

### Step 4: Manager Review

Numbers don't tell the whole story. The Manager Review is where the human supervisor provides subjective feedback:
- A rating from 1 to 5 (Needs Improvement to Outstanding)
- Written comments or an improvement plan
- The review period (e.g., Q4 2026)

**The Trigger:** When the manager clicks "Submit Review", the system automatically runs a full evaluation in the background — gathering the human baseline, KRA weights, and manager feedback to calculate the AI's final score across all 7 dimensions.

**URL:** `http://localhost:8000/widget/manager-review.html`

---

### Step 5: Automated Evaluation (Behind the Scenes)

Once the manager submits their review, the backend automatically:
1. Reads the human baseline and KRA weights from the database
2. Runs the AI through telemetry evaluations (Jaeger, Zipkin, DeepEval, etc.)
3. Calculates all 7 dimension scores
4. Applies safety gates and compliance checks
5. Pushes the final score to the live dashboard

This is completely hands-free — no terminal commands or manual intervention required.

---

### Step 6: The DPI-LS Dashboard

All results flow into the live Dashboard, which serves as your central command center. The Dashboard has four main sections:

| Section | What It Shows |
|---------|---------------|
| **Dashboard** | The main leaderboard — all agents ranked by score with a breakdown of all 7 dimensions |
| **Resources** | Documentation, operations manuals, and help guides |
| **DPI-LS Score** | Detailed scoring methodology and historical score trends |
| **Submit Customer Feedback** | A portal for end-users to submit feedback, which feeds into the Quality score |

**URL:** `http://localhost:8000/widget/demo.html`

---

## Business Architecture

The complete end-to-end workflow follows this architecture:

```
Agent Onboarding → KRA Configuration → Static Data Configuration → Manager Review
                                                                        ↓
                                                            Event-Driven Automation
                                                                        ↓
                                                              DPI-LS Dashboard
                                                         ┌──────────────────────────┐
                                                         │  Leaderboard             │
                                                         │  Resources               │
                                                         │  DPI-LS Score Details     │
                                                         │  Customer Feedback Portal │
                                                         └──────────────────────────┘
```

For a detailed architecture document with phase descriptions, see [dpi_ls_business_architecture.md](./dpi_ls_business_architecture.md).

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **uv** (Python package manager)

### Start the Server

```bash
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Then open your browser:
- **Onboarding:** http://127.0.0.1:8000/widget/onboarding.html
- **Dashboard:** http://127.0.0.1:8000/widget/demo.html
- **API Docs:** http://127.0.0.1:8000/docs

### Register a New Agent

You can register a new agent via the API:

```bash
curl -X POST http://127.0.0.1:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent-001", "agent_name": "My First Agent", "status": "ACTIVE"}'
```

Then follow the 6-step workflow through the web interface to onboard, configure, and evaluate your agent.

---

## Supported AI Frameworks

DPI-LS is framework-agnostic. It works with any AI framework including:

| Framework | Support Level |
|-----------|--------------|
| OpenAI Agents SDK | Full auto-detection |
| LangGraph | Full auto-detection |
| LangChain | Full auto-detection |
| CrewAI | Full auto-detection |
| AutoGen | Full auto-detection |
| LlamaIndex | Full auto-detection |
| Raw OpenAI / Anthropic | Full auto-detection |
| Any custom framework | Best-effort fallback |

---

## Observability Integrations

DPI-LS integrates with industry-standard observability tools:

| Category | Tools |
|----------|-------|
| **Tracing** | Jaeger, Zipkin, OpenTelemetry, Grafana Tempo |
| **Quality Evaluation** | LangSmith, Ragas, AgentOps, DeepEval |
| **Execution Monitoring** | Langfuse, Phoenix, Traceloop |
| **Cost Monitoring** | OpenLIT, OpenCost, Prometheus |
| **Governance** | LLM Guard, Rebuff, TruLens, Microsoft Presidio, Detect-Secrets |
| **Policy Compliance** | Open Policy Agent (OPA) |

---

## Key Features

- **Single Score** — One number (0–100) that a CFO can quote, with full 7-dimension breakdown available
- **Safety Gates** — Automatic compliance enforcement; a single PII leak flags the agent as Unsafe
- **Event-Driven** — Manager review triggers automatic scoring; no manual commands needed
- **Live Dashboard** — Real-time leaderboard with an airport departure board style display
- **Framework Agnostic** — Works with any AI framework without code changes
- **Human-in-the-Loop** — Blends objective AI metrics with subjective human manager feedback

---

## Project Structure

```
dpi-ls/
├── api/              API server (FastAPI) — routes, scoring, metrics
├── contract/         Data models — the canonical schemas
├── engine/           Pure scoring engine — 7 dimension calculations
├── dpi_ls/           Installable package — monitor, evaluate, collect
├── ingestion/        Adapters — connects to external data sources
├── store/            Database layer (SQLAlchemy)
├── widget/           Web dashboard — HTML, CSS, JavaScript
├── examples/         Demo agents for every supported framework
├── tests/            274 test functions across 44 test files
├── fixtures/         Sample data for testing
├── scripts/          Utility scripts
└── README.md         This file
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./dpi_ls.db` | Database connection string |
| `WIDGET_ALLOWED_ORIGINS` | `*` | CORS allowlist for the dashboard |
| `JAEGER_ENDPOINT` | `http://127.0.0.1:14268` | Jaeger tracing endpoint |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus metrics endpoint |
| `GRAFANA_URL` | `http://localhost:3000` | Grafana dashboard endpoint |

---

## Running Tests

```bash
uv run pytest
```

274 test functions across 44 test files — runs in under 12 seconds.

---

## Documentation

- **[Business Architecture](./dpi_ls_business_architecture.md)** — Detailed workflow phases and architecture diagram
- **[Design Rationale](./CLAUDE.md)** — Technical design decisions and scoring specification
- **[API Documentation](http://localhost:8000/docs)** — Interactive Swagger UI (when server is running)

---

## License

Proprietary — Intelligenz IT

---

*Built with ❤️ for Life Sciences AI Governance*
