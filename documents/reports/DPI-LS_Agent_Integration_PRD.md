# Product Requirements Document (PRD): Real Agent Integration with DPI-LS

## 1. Overview and Security Architecture
Because enterprise AI agents (like **Chandra**) operate behind strict security guardrails, data privacy policies, and compliance firewalls, **DPI-LS operates strictly as a Secure Push System.** 

External scoring engines cannot securely "pull" data from an agent. Instead, the agent is equipped with a lightweight wrapper that securely **pushes** standard OpenTelemetry metrics (traces, token counts, execution times, safety flags) to the DPI-LS backend. DPI-LS then calculates the score without ever exposing the agent's sensitive core logic or restricted data.

---

## 2. End-to-End Integration Workflow

The process of connecting a real agent to DPI-LS and generating an official L1-L5 Maturity Score involves two distinct phases: **Business Registration** and **Code Integration**.

### Phase 1: Business Registration (The Business Owner)
Before the agent writes any code, the Business Owner must define what "success" looks like for this specific agent.

1. **Navigate to the DPI-LS Portal:** Open the Dashboard (`/widget/demo.html`).
2. **Onboarding:** Click **"Onboard Agent"**.
   - Enter the exact Agent ID (e.g., `chandra-finops`).
   - Fill out the role, environment, and owner details.
3. **Configuration (Weightages):** After submitting, you are taken to the **Configuration Page**.
   - The Business Owner allocates exactly 100 points across the 7 parameters (Productivity, Quality, Efficiency, Governance, Risk, Validation, Cost).
   - *Example: A financial bot may require 30% Risk and 25% Quality.*
4. **Save:** The configuration is saved to the DPI-LS SQLite Database. The system is now waiting to receive telemetry for `chandra-finops`.

---

### Phase 2: Technical Code Integration (The Development Team)
The developers of the Chandra agent do not need to rewrite their agent. They simply inject a secure telemetry wrapper into their existing code.

**Where to add the code:**
You must add this to the primary entry-point file where the Chandra agent is initialized and executed. 
*   **Typical Folder:** `src/agent/` or `app/`
*   **Typical File:** `main.py`, `app.py`, or `chandra_bot.py`

**What exactly to add (Lines of Code):**
Locate the section of the code where the agent object/workflow is instantiated. Add the following lines:

```python
# --- ADD THIS TO THE TOP OF THE FILE (IMPORTS) ---
import dpi_ls

# ... (Existing Chandra Agent Initialization Code) ...
agent = YourChandraAgent(...) 

# --- ADD THIS DIRECTLY BELOW THE AGENT INITIALIZATION ---
# This wraps the agent in the secure telemetry monitor
collector = dpi_ls.monitor(
    agent, 
    agent_id="chandra-finops",       # MUST match the ID registered in the UI
    agent_name="Chandra FinOps",
    host="<IP_ADDRESS_OF_DPI_LS_SERVER>", 
    port=8000
)

# ... (Existing Code: Agent executes its prompt/query) ...
```

---

## 3. How the Measurement & Scoring Actually Happens

Once those two lines of code are added, here is how the score is generated:

1. **Execution:** A user asks the Chandra agent a question.
2. **Telemetry Capture:** As Chandra thinks and responds, the `dpi_ls.monitor` wrapper invisibly captures:
   - *Cost & Efficiency:* Token usage and API latency.
   - *Quality & Validation:* Hallucination checks, groundedness, and response tracing.
   - *Risk & Governance:* Policy violations, prompt injection attempts, or unapproved data access.
3. **The Push:** The wrapper pushes this payload to the DPI-LS backend endpoint (`POST /api/agents/chandra-finops/ingest`).
4. **The Scoring Engine:** The DPI-LS backend (`api/scoring.py`) catches the payload. It queries the database for the Business Owner's custom weightages (saved in Phase 1). It mathematically multiplies the telemetry metrics by the weightages to generate the final 0-100 `dpi_ls_score`.
5. **Dashboard Visualization:** 
   - When the user clicks on the **Dashboard**, they see Chandra's real-time score.
   - When the user clicks on Chandra's name, they are taken to the **Profile Section**. Here, the 0-100 score is translated into a **Maturity Band (L1 to L5)**, visually showing the exact strengths and weaknesses of the agent.
