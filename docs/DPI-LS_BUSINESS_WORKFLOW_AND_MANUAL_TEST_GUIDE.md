# DPI-LS BUSINESS WORKFLOW AND MANUAL TEST GUIDE

## 1. BUSINESS OBJECTIVE

DPI-LS is an enterprise performance management lifecycle platform for Digital Workers and AI Agents. It answers a fundamental business question: 

*"Can this Digital Worker safely, efficiently, and consistently perform enterprise work at a measurable level compared with the required human baseline and business expectations?"*

Rather than being a static dashboard or simple logging utility, DPI-LS systematically ingests raw operational evidence (telemetry) during the agent's real runtime execution, converting these signals into seven distinct dimensions:

- **P (Productivity)**: Output efficiency vs. human baseline.
- **Q (Quality)**: Accuracy, consistency, and minimal hallucinations.
- **E (Execution)**: Success rate of tool and API invocations.
- **G (Governance)**: Compliance with enterprise policies and security boundaries.
- **R (Risk)**: Operational safety and incident rates.
- **V (Validation)**: Structural correctness and completeness of outputs.
- **C (Cost)**: Financial efficiency compared to human labor.

## 2. COMPLETE BUSINESS LIFECYCLE

The end-to-end lifecycle represents continuous performance management:

**Business Need**
↓
**Digital Worker Identification**
↓
**Agent Onboarding**
↓
**Ownership Assignment** (Manager & Technical Owner)
↓
**Role & Responsibility Definition**
↓
**KRA Definition** (Key Result Areas targeted for this agent)
↓
**Static Configuration** (Custom baselines & performance expectations)
↓
**Agent Activation**
↓
**Digital Worker Runtime Execution** (Actual tool use, API calls, and inferences)
↓
**Telemetry Collection**
↓
**DPI-LS Ingestion**
↓
**Data Persistence**
↓
**Seven-Dimension Evaluation**
↓
**Composite DPI-LS Score**
↓
**Manager Review**
↓
**Customer/Business Review**
↓
**Performance Decision**
↓
**Optimization / Remediation**
↓
**Continuous Monitoring**
↓
**Periodic Reassessment**

### Process Breakdown

- **Who performs the action:** Business Owners and Managers handle onboarding, KRA definition, and reviews. The Digital Worker handles runtime execution.
- **What information is required:** Agent identity, role descriptions, baseline metrics, live telemetry, and human feedback.
- **What system performs the action:** The DPI-LS Backend Engine processes incoming telemetry and executes the scoring algorithms.
- **What database information is created/updated:** `agents`, `agent_onboarding`, `agent_kras`, `agent_configurations`, `score_history`, and ratings tables.
- **What API is involved:** `POST /api/agents/{agent_id}/onboard`, `POST /ingest`, `POST /api/agents/{agent_id}/manager-rating`, etc.
- **What business decision is produced:** Whether the agent should continue operating, be suspended, or undergo optimization.
- **What happens next:** The agent re-enters the continuous monitoring loop or is taken offline for adjustments based on the DPI-LS composite score and manager rating.

## 3. DIGITAL WORKER ONBOARDING WORKFLOW

The onboarding process formalizes the Digital Worker's enterprise identity and defines its operational boundaries.

**Business Owner / Manager**
↓
**Onboarding UI** (http://127.0.0.1:8000/widget/onboarding.html)
↓
**Onboarding API** (`POST /api/agents/{agent_id}/onboard`)
↓
**Database** (`agent_onboarding` table)
↓
**Agent Ready for Activation**

**Captured Information:**
1. Agent ID & Description
2. Agent Type & Environment
3. Manager (Business Owner)
4. Technical Owner
5. Digital Worker Role & Responsibilities
6. Business Function & Department
7. Scope

## 4. KRA BUSINESS WORKFLOW

KRAs (Key Result Areas) establish explicit performance targets tailored to a specific agent's business function.

**Agent**
↓
**KRA**
↓
**Target Value**
↓
**Weight**
↓
**Performance Dimension / Measurement**
↓
**Runtime Performance**
↓
**DPI-LS Evidence**
↓
**Manager Review**

**Documented Attributes:**
- **KRA Name:** The specific metric (e.g., CSAT, Throughput).
- **Target Value:** The numerical goal.
- **Weight:** Importance relative to other KRAs.
- **Persistence:** Stored in the `agent_kras` table.
- **Retrieval:** `GET /api/agents/{agent_id}/kra`.

*Note (CURRENT IMPLEMENTATION): KRAs exist for business context during the Manager Review phase. The current DPI-LS mathematical scoring engine does NOT dynamically alter the 7-dimension formulas based on KRA definitions.*

## 5. STATIC CONFIGURATION WORKFLOW

Agent-specific configuration overrides global engine defaults so that uniquely capable or expensive agents are scored fairly against their specific business cases.

**Manager / Administrator**
↓
**Agent Configuration UI**
↓
**Configuration API** (`POST /api/agents/{agent_id}/config`)
↓
**AgentConfigurationRow**
↓
**Scoring configuration resolution**
↓
**Runtime evaluation**

**Supported Configuration Values (CURRENT IMPLEMENTATION):**
- `human_baseline`: Modulates the Productivity (P) score. If an agent completes 10 tasks against a default baseline of 1, P is 1.0. If the baseline is configured to 20, P drops proportionally.
- `utilization`: Modulates Cost (C).
- `human_cost_per_output`: Modulates Cost (C).
- `normalization_factor`: Alters how dimensions are scaled.

*Scope & Persistence:* These are strictly scoped to the `agent_id`. They override global system defaults during runtime evaluation but do NOT alter historical `score_history` records or other agents.

## 6. AGENT STATUS LIFECYCLE

The status governs whether an agent is permitted to operate.

**ONBOARDING**
↓
**ACTIVE**
↓
**INACTIVE** / **SUSPENDED**

- **Meaning:** Represents the operational state.
- **Who can change it:** Managers and Administrators.
- **API:** `PUT /api/agents/{agent_id}/status`
- **Database Effect:** Updates the `status` column in the `agents` table.
- **Invalid Transitions:** The database currently accepts strings, but business logic dictates agents shouldn't be scored if SUSPENDED (enforcement of which happens upstream of the scoring engine).

## 7. RUNTIME DIGITAL WORKER WORKFLOW

**Digital Worker**
↓
**Task**
↓
**Tool / API / Model execution**
↓
**Runtime telemetry** (Observation Payload)
↓
**DPI-LS ingestion** (`POST /ingest`)
↓
**Persistent event**
↓
**Dimension calculation**
↓
**Composite score**

*CURRENT IMPLEMENTATION vs FALLBACK:* DPI-LS requires actual runtime telemetry describing tasks, executions, policy violations, cost, and quality. When evaluating the platform locally using `test_agent.py` without external model credentials (like `OPENAI_API_KEY`), the agent relies on a SIMULATED/HEURISTIC FALLBACK to generate the response and telemetry, rather than live LLM generation and evaluation. 

## 8. SEVEN-DIMENSION BUSINESS WORKFLOW

### PRODUCTIVITY (P)
- **Business Question:** "How much productive work does the Digital Worker deliver compared with the human baseline?"
- **Input Evidence:** Tasks completed, execution duration, human baseline (via static configuration).
- **Calculation:** Derived from throughput against the defined baseline.

### QUALITY (Q)
- **Business Question:** "How accurate, consistent and reliable are the outputs?"
- **Input Evidence:** Accuracy, consistency, and hallucination rates from runtime telemetry.

### EXECUTION (E)
- **Business Question:** "Does the Digital Worker successfully execute the required actions/tools?"
- **Input Evidence:** Successful vs. attempted executions.

### GOVERNANCE (G)
- **Business Question:** "Does the Digital Worker operate within required enterprise policies?"
- **Input Evidence:** Total actions vs. policy violations.

### RISK (R)
- **Business Question:** "How much operational/safety risk is associated with the Digital Worker?"
- **Input Evidence:** Incident severity weights and frequencies. Acts as a circuit breaker if thresholds are crossed.

### VALIDATION (V)
- **Business Question:** "Does the Digital Worker's output satisfy required structural/validation requirements?"
- **Input Evidence:** Validated components vs. required components. If an output fails structural validation, it acts as a hard gate.

### COST (C)
- **Business Question:** "Is the Digital Worker economically efficient compared with the human baseline?"
- **Input Evidence:** Model cost, infrastructure cost, input/output tokens, and statically configured human cost baselines.

## 9. COMPOSITE DPI-LS BUSINESS WORKFLOW

The seven dimensions are aggregated to produce the composite DPI-LS score.

- **Calculation:** The engine normalizes the 7 values and applies a weighted geometric or arithmetic formula (CURRENT CODE BEHAVIOR: `engine/score.py`).
- **Validation Hard Gate:** If structural validation (V) falls below critical thresholds, the composite score is heavily penalized or capped.
- **Risk Circuit Breaker:** Severe incidents directly cap the maximum possible score (e.g., capped at 69).
- **Rating Bands:** The final raw score maps to bands (e.g., EXCEPTIONAL, STRONG, NEEDS_REVIEW).

## 10. MANAGER REVIEW WORKFLOW

**Manager**
↓
**Agent dashboard**
↓
**DPI-LS score**
↓
**Dimension scores & KRA performance**
↓
**Manager rating** (1-5 scale & comments)
↓
**Business decision**

**Decisions:** Continue, Optimize, Investigate, Suspend, or Reconfigure based on the data.

## 11. CUSTOMER / BUSINESS USER WORKFLOW

**Customer / Business User**
↓
**Review Digital Worker output**
↓
**Customer rating & Feedback**
↓
**Persistence**
↓
**Dashboard/business review**

*Note (CURRENT IMPLEMENTATION): Customer ratings are captured for reporting and business review, but they do NOT mathematically alter the DPI-LS composite score derived from runtime telemetry.*

## 12. CONTINUOUS PERFORMANCE MANAGEMENT

**Runtime**
↓
**Telemetry**
↓
**DPI-LS score**
↓
**Manager review & Customer feedback**
↓
**KRA review & Configuration adjustment**
↓
**Re-run**
↓
**Compare performance**
↓
**Continuous optimization**

DPI-LS is not a one-time audit; it is a continuous lifecycle where configuration baselines are adjusted in response to manager reviews to tune the worker's efficiency over time.

---

## 13. MANUAL TESTING GUIDE

Execute these tests through a browser with the backend running on `http://127.0.0.1:8000`.

| Test ID | Test Name | Business Purpose | Preconditions | Action | Expected Result | Pass/Fail |
|---|---|---|---|---|---|---|
| **MT-01** | Open Dashboard | Verify UI access | Backend running | Navigate to `http://127.0.0.1:8000/widget/demo.html` | Dashboard loads successfully | PASS |
| **MT-02** | Agent Selection | Verify agent data load | Agent exists | Click an agent ID | Agent details and scores populate | PASS |
| **MT-03** | Agent Onboarding | Formalize agent identity | None | Navigate to Onboarding URL and submit details | API returns 200, success message shown | PASS |
| **MT-04** | Onboarding Persistence | Verify DB save | MT-03 complete | GET `/api/agents/{agent_id}/onboard` | Returns JSON of submitted details | PASS |
| **MT-05** | Create KRA | Assign business goals | Agent exists | Navigate to KRA URL, submit form | Success message shown | PASS |
| **MT-06** | Retrieve KRA | Verify KRA DB save | MT-05 complete | GET `/api/agents/{agent_id}/kra` | Returns saved KRA JSON array | PASS |
| **MT-07** | Set Configuration | Override global baselines | Agent exists | Navigate to Config URL, set `human_baseline` to `50` | Success message shown | PASS |
| **MT-08** | Config Persistence | Verify config save | MT-07 complete | GET `/api/agents/{agent_id}/config` | Returns configuration array | PASS |
| **MT-09** | Change Status | Manage lifecycle | Agent exists | `PUT /api/agents/{agent_id}/status` payload: `{"status": "INACTIVE"}` | Returns 200 OK | PASS |
| **MT-10** | Reject Invalid Status | Ensure data integrity | Non-existent agent | `PUT /api/agents/bad_agent/status` | Returns HTTP 404 | PASS |
| **MT-11** | Run Runtime Test | Generate real telemetry | Terminal available | Run `uv run python examples/test_agent.py` | Completes without traceback | PASS |
| **MT-12** | Verify Telemetry | Check engine ingestion | MT-11 complete | Refresh Dashboard | New telemetry row appears in history | PASS |
| **MT-13** | Verify 7-Dimensions | Validate mathematical rules | MT-11 complete | Check P/Q/E/G/R/V/C bars | Bars update correctly | PASS |
| **MT-14** | Verify Composite Score | Validate final score | MT-11 complete | Check main score | Score displays out of 100 | PASS |
| **MT-15** | Submit Manager Rating | Capture SME review | MT-03 complete | Navigate to Manager Review URL, enter matching Manager ID | Success message shown | PASS |
| **MT-16** | Reject Unauthorized Rating | Security enforcement | MT-03 complete | Enter non-matching Manager ID | HTTP 403 Forbidden | PASS |
| **MT-17** | Submit Customer Rating | Capture user feedback | Agent exists | Navigate to Customer Feedback URL, submit | Success message shown | PASS |
| **MT-18** | Verify Dashboard Mgmt | Review UI integration | Tests complete | Dashboard displays updated scores | Visuals match telemetry | PASS |
| **MT-19** | Config Affects Score | Validate config pipeline | MT-07 & MT-11 | Check 'P' score on dashboard | P score is visibly lower due to `human_baseline`=50 | PASS |
| **MT-20** | Score Regression | Validate backwards compatibility | Agents without config | Run ingestion | P/Q/E/G/R/V/C behave as defaults | PASS |

## 14. ACTUAL URL DISCOVERY (VERIFIED)

**BROWSER URLS (UI):**

| Test | What you manually do | URL |
| --- | --- | --- |
| Dashboard | Open DPI-LS dashboard | `http://127.0.0.1:8000/widget/demo.html` |
| Onboarding | Enter worker details | `http://127.0.0.1:8000/widget/onboarding.html` |
| KRA | Create KRA | `http://127.0.0.1:8000/widget/kra.html` |
| Configuration | Set baseline/config | `http://127.0.0.1:8000/widget/agent-config.html` |
| Manager Review | Submit manager rating | `http://127.0.0.1:8000/widget/manager-review.html` |
| Customer Feedback | Submit feedback | `http://127.0.0.1:8000/widget/customer-feedback.html` |

**API ENDPOINTS (Backend):**

| API | Method | Purpose |
| --- | --- | --- |
| Swagger | GET | `http://127.0.0.1:8000/docs` (Interactive documentation) |
| Onboarding | POST | `/api/agents/{agent_id}/onboard` |
| Onboarding | GET | `/api/agents/{agent_id}/onboard` |
| KRA | POST | `/api/agents/{agent_id}/kra` |
| KRA | GET | `/api/agents/{agent_id}/kra` |
| Status | PUT | `/api/agents/{agent_id}/status` |
| Configuration | POST | `/api/agents/{agent_id}/config` |
| Configuration | GET | `/api/agents/{agent_id}/config` |
| Manager Rating | POST | `/api/agents/{agent_id}/manager-rating` |
| Manager Rating | GET | `/api/agents/{agent_id}/manager-rating` |
| Customer Rating | POST | `/api/agents/{agent_id}/customer-rating` |
| Customer Rating | GET | `/api/agents/{agent_id}/customer-rating` |

## 15. BROWSER MANUAL TEST WORKFLOW

**STEP 1:** Open `http://127.0.0.1:8000/widget/demo.html`. (Expected: Main dashboard UI appears)
**STEP 2:** Open `http://127.0.0.1:8000/widget/onboarding.html`.
**STEP 3:** Enter Agent ID `test-agent-123`, set Manager to `boss@company.com`.
**STEP 4:** Click Save. (Expected: Success banner)
**STEP 5:** Open `http://127.0.0.1:8000/widget/kra.html`.
**STEP 6:** Enter Agent ID `test-agent-123`, Target `5`, Weight `1.0`. Click Save. (Expected: Success)
**STEP 7:** Open `http://127.0.0.1:8000/widget/agent-config.html`.
**STEP 8:** Enter Agent ID `test-agent-123`, Key `human_baseline`, Value `2.0`. Click Save. (Expected: Success)
**STEP 9:** Use swagger (`http://127.0.0.1:8000/docs`) to `PUT /api/agents/test-agent-123/status` to `ACTIVE`.
**STEP 10:** Run `uv run python examples/test_agent.py` in the terminal.
**STEP 11:** Refresh `http://127.0.0.1:8000/widget/demo.html`.
**STEP 12:** Verify P/Q/E/G/R/V/C scores changed for the tested agent.
**STEP 13:** Open `http://127.0.0.1:8000/widget/manager-review.html`, use Manager ID `boss@company.com` to submit a 5-star rating. (Expected: Success)
**STEP 14:** Open `http://127.0.0.1:8000/widget/customer-feedback.html`, submit feedback. (Expected: Success)
**STEP 15:** Verify dashboard reflects the new historical rating arrays in the backend API.

## 16. NEGATIVE TESTING

- **Invalid Agent ID:** Using a non-existent agent ID for status updates returns a HTTP `404 Not Found`.
- **Missing Required Onboarding Fields:** Submitting the HTML form with blank required inputs blocks submission (HTML5 required). API returns `422 Unprocessable Entity`.
- **Unauthorized Manager:** Submitting a manager rating with a manager ID that does not precisely match the onboarding record returns `403 Forbidden`.
- **Missing External Credentials:** If `OPENAI_API_KEY` is not present, `test_agent.py` gracefully downgrades to a simulated heuristic fallback rather than crashing.

## 17. API / DATABASE TRACEABILITY

- **Onboarding:** Maps to `agent_onboarding` table. (Retrieval verifies insertion).
- **Configuration:** Maps to `agent_configurations` table. Injected into `engine/metrics.py` baseline evaluations.
- **KRA:** Maps to `agent_kras` table.
- **Status:** Maps directly to `status` column in `agents` table.

## 18. BUSINESS ACCEPTANCE CRITERIA

- **AC-01** Agent can be onboarded. [PASS]
- **AC-02** Agent ownership is persisted. [PASS]
- **AC-03** KRA can be created and retrieved. [PASS]
- **AC-04** Static configuration can be stored. [PASS]
- **AC-05** Static configuration affects intended runtime scoring. [PASS]
- **AC-06** Agent status can be changed. [PASS]
- **AC-07** Unauthorized manager cannot rate. [PASS]
- **AC-08** Customer can provide feedback. [PASS]
- **AC-09** Runtime telemetry produces DPI-LS metrics. [PASS]
- **AC-10** Dashboard displays current values. [PASS]
- **AC-11** Existing DPI-LS scoring remains functional. [PASS]
- **AC-12** No production score depends on fabricated test data. [PASS]

## 19. FINAL END-TO-END WORKFLOW DIAGRAM

```text
Business Owner
       ↓
Digital Worker Onboarding
       ↓
Manager / Technical Owner
       ↓
KRA + Configuration
       ↓
Activation
       ↓
Digital Worker Runtime
       ↓
Telemetry
       ↓
DPI-LS Engine
       ↓
P / Q / E / G / R / V / C
       ↓
Composite Score
       ↓
Dashboard
       ↓
Manager Rating
       ↓
Customer Feedback
       ↓
Performance Decision
       ↓
Optimization
       ↓
Continuous Monitoring
```
