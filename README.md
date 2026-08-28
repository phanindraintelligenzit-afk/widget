<div align="center">

# DPI-LS Digital FTE Performance Index for Life Sciences

<p align="center">A comprehensive enterprise-grade solution by Intelligenz IT.</p>

<p align="center">
<a href="https://intelligenzit.com/"><img src="https://img.shields.io/badge/Intelligenz_IT-green?style=flat-square" alt="Organization"/></a>
<a href="https://www.linkedin.com/company/intelligenz-it/"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin" alt="LinkedIn"/></a>
</p>

<p align="center">
<a href="#quick-start"><b>Quick Start</b></a> • <a href="./dpi_ls_business_architecture.md"><b>Architecture</b></a> • <a href="#dashboard"><b>Dashboard</b></a> • <a href="#the-7-dimensions"><b>The 7 Dimensions</b></a>
</p>

</div>

---

Prepared by Intelligenz IT AI & Automation Center of Excellence

## Quick Start

```bash
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```
- **Onboarding:** http://127.0.0.1:8000/widget/onboarding.html
- **Dashboard:** http://127.0.0.1:8000/widget/demo.html
- **API Docs:** http://127.0.0.1:8000/docs

## Business Problem

When companies deploy AI to handle important work — like processing invoices, analyzing medical documents, or monitoring cloud costs — they need to know if the AI is doing a good job, working safely, and actually saving money. The problem is a lack of real-time visibility, governance, and quantifiable metrics on AI behavior.

## Solution Overview

**DPI-LS answers that question.** Instead of just hoping the AI works, DPI-LS automatically measures 7 critical performance areas and gives you a single, easy-to-understand score out of 100. It combines hard data from the AI's operations with subjective feedback from human managers to ensure the AI is truly adding value. 

**We measure Trust, not just Productivity.** By bridging HR, Business, and Compliance, DPI-LS helps organizations manage AI as a workforce — with full lifecycle governance and accountability.

## Recent Technical Upgrades (Frontend & Widget UI)

The widget platform has undergone a major **UI/UX and Technical Architecture Overhaul** to transition the application into a dark-themed, enterprise-ready dashboard with enhanced AI features.

### 1. Universal Layout & Routing
* **Dark Theme Standard**: Deprecated old color schemes in favor of a unified `#090d16` and `#0f172a` deep-space dark theme across all 7 views.
* **Unified Sidebar Navigation**: Reordered and strictly locked the sidebar navigation exactly as requested: `Dashboard` (Default Landing) -> `Onboard Agent` -> `Configuration` -> `Rating` -> `Profile` -> `Resources` -> `Sign Out`.
* **Login Tracker**: Embedded a persistent session tracker securely bound to `localStorage` during the `/widget/admin-login.html` authentication step. The `Session Started` badge renders dynamically in the header of all pages.

### 2. Intelligent Search & Autocomplete
* **Global Search Component**: Added a persistent top header with a search bar.
* **Live Autocomplete**: Injected a vanilla JS event-driven listener to the search bar. Typing instantly triggers an async fetch to `/api/ratings`, filtering and categorizing results live into `Agents` and `Metrics`.
* **Deep Linking**: Clickable autocomplete dropdown results route the user instantly to heavily parameterized URLs (e.g. `agent-profile.html?id=chandra-finops` or `demo.html?filter=risk`).

### 3. Native AI Chatbot Integration
* **Floating Assistant**: Injected an absolute-positioned floating action button (FAB) bound to a slide-up conversational interface.
* **Context-Aware Responses**: Bound to a simulated logic engine that provides immediate explanations for complex topics like the DPI-LS algorithm, Risk thresholds, and Weightages.
* **Typewriter Effect**: AI responses use a `setInterval`-based streaming character renderer to simulate natural language generation block-by-block.

### 4. Dynamic Metric Visualization
* **Conditional Score Rendering**: Re-wrote the inner polling loop in `dpi-ls.js` to dynamically inject inline CSS colors to the final DPI-LS score cells.
  * Score >= 80: **Green**
  * Score 51 - 79: **Yellow**
  * Score <= 50: **Red**
* **Strict Configuration Constraints**: Overhauled the `agent-config.html` UI to accept all 7 specific dimensions (P, Q, E, G, R, C, V). Added hard validation logic ensuring weight distribution equals exactly 100% prior to dispatching `Promise.all` fetch payloads to the backend.

### 5. Backend Alignment
* **Test Suite Modernization**: Re-wired `tests/test_widget_serving.py` to correctly test the new requirement that unauthenticated root (`/`) visitors are routed strictly to `admin-login.html` instead of the Dashboard.

## Architecture

The complete end-to-end workflow follows this architecture:

```mermaid
flowchart TD
    %% Define Global Styles
    classDef primary fill:#0033A0,stroke:#002277,stroke-width:3px,color:#ffffff,font-weight:bold,rx:10px,ry:10px;
    classDef secondary fill:#007BFF,stroke:#0056b3,stroke-width:2px,color:#ffffff,rx:8px,ry:8px;
    classDef database fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#000000;
    classDef dashboard fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#000000;
    classDef userAction fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#000000,stroke-dasharray: 5 5;
    classDef security fill:#FF5722,stroke:#BF360C,stroke-width:3px,color:#ffffff,font-weight:bold,rx:10px,ry:10px;
    
    %% Main Nodes
    subgraph Phase 0: Security [Phase 0: Authentication & RBAC]
        direction TB
        L([0a. User Login]):::security
        R{0b. RBAC Verification<br/>Admin/Manager/Customer}:::security
    end

    subgraph Phase 1: Preparation [Phase 1: Agent & Data Configuration]
        direction TB
        A([1. Agent Onboarding]):::primary
        B([2. KRA Configuration]):::primary
        C([3. Static Data Config]):::primary
    end

    subgraph Phase 2: Evaluation [Phase 2: Human & Machine Evaluation]
        direction TB
        D([4. Manager Review]):::userAction
        E{5. Event-Driven<br/>Telemetry Trigger}:::secondary
        F[(Database<br/>Aggregation & Engine)]:::database
    end
    
    subgraph Phase 3: Visibility [Phase 3: Executive Visibility]
        direction TB
        G[[6. DPI-LS Live Dashboard]]:::dashboard
        G1(Main Leaderboard)
        G2(Resources Hub)
        G3(Score Analytics)
        G4(Feedback Portal)
        G5(Agent Profile View)
    end
    
    subgraph Phase 4: Termination [Phase 4: Session End]
        direction TB
        H([7. Logout Session]):::security
        L2([8. Return to Login]):::security
    end

    %% Connections
    L -->|Validates JWT Credentials| R
    R -->|Authorizes Specific Roles| A
    
    A -->|Registers Identity & Ownership| B
    B -->|Defines Target Metrics| C
    C -->|Sets Human Baselines| D
    
    D -->|Submits SME Rating 1 to 5| E
    E -->|Background Execution| F
    F -->|Calculates 7 Dimensions| G
    
    G --- G1
    G --- G2
    G --- G3
    G --- G4
    G --- G5
    
    G4 -->|Auto-Redirect on Submit| G5
    G1 -->|Click Agent Name| G5
    
    G -->|Click Logout| H
    G5 -->|Click Logout| H
    H -->|Clears JWT Token| L2
```

For detailed architecture diagrams and the event-driven workflow, please refer to the dedicated document:
[DPI-LS Business Architecture Document](./dpi_ls_business_architecture.md)

## Dashboard

All results flow into the live Dashboard, which serves as your central command center. The Dashboard contains:
- **Leaderboard**: All agents ranked by score.
- **Resources**: Operational manuals and guides.
- **DPI-LS Score Details**: Scoring methodology.
- **Customer Feedback Portal**: End-user feedback forms.

[Dashboard Reference](./docs/dashboard.png)

## KPIs

- **Score Range**: 0-100 arithmetic mean of all dimensions.
- **Exceptional**: 85-100
- **Strong**: 70-84
- **Needs Optimization**: 50-69
- **Underperforming**: Below 50

## The 7 Dimensions

Every AI agent is evaluated across these 7 areas:

| Dimension | What It Measures | In Simple Terms |
|-----------|-----------------|-----------------|
| **P** — Productivity | How much work the AI completes compared to a human | "Is the AI faster than a person?" |
| **Q** — Quality | Accuracy, consistency, and hallucination rate of AI outputs | "Is the AI giving correct answers?" |
| **E** — Execution | Success rate of all AI tasks and tool calls | "Is the AI completing tasks without errors?" |
| **G** — Governance | Policy compliance — PII leaks, unauthorized access | "Is the AI following the rules?" |
| **R** — Risk | Frequency and severity of incidents and exceptions | "Is the AI causing any problems?" |
| **V** — Validation | Whether outputs are properly structured | "Is the AI producing well-formatted results?" |
| **C** — Cost | AI cost per output compared to human cost per output | "Is the AI saving us money?" |

## AI Agent Model

The engine is **agent-agnostic** — it consumes a canonical `AgentObservation` schema and never imports an agent framework. It supports:
- OpenAI Agents SDK
- LangGraph, LangChain, CrewAI, AutoGen, LlamaIndex
- Raw OpenAI / Anthropic
- Any custom framework

## Security & Governance

If the AI fails on Governance (G), Risk (R), or Validation (V), the system automatically caps the score and flags the agent as **Unsafe** — no matter how well it performs in other areas. A single PII leak will trigger this safety gate.

## Deployment

Deploy using Docker Compose for the full observability stack:
```bash
docker compose up -d
```

## References

- [Whitepaper](./docs/whitepaper.pdf)
- [Design Rationale](./CLAUDE.md)
- [License](./LICENSE)


## About Intelligenz IT

Intelligenz IT is a global enterprise transformation partner specializing in:

- AI & Automation
- Microsoft Copilot
- Copilot Studio
- Azure OpenAI
- SAP
- Salesforce
- ServiceNow
- Cloud Transformation
- Data Engineering
- Analytics
- Enterprise Architecture

Website: https://intelligenzit.com/  
LinkedIn: https://www.linkedin.com/company/intelligenz-it/

---

© Intelligenz IT.
All Rights Reserved.

For inquiries:
https://intelligenzit.com/

LinkedIn:
https://www.linkedin.com/company/intelligenz-it/
