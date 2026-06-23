# DPI-LS — Validation Resource Data Sources
**Final Presentation Version**

## 1. Resource Catalogue Integration (Validation focus)

| Resource Name | Category | Purpose | Implementation Status |
|---|---|---|---|
| **OpenTelemetry (OTel)** | Instrumentation Standard | Standardized traces, metrics, and logs instrumentation across the agent. | Implemented (Foundational) |
| **Prometheus** | Metrics Store | Test-run success/failure counters and validation-job metrics. | Implemented (Recommended) |
| **Grafana** | Metrics Visualization | Visualization of validation pass/fail and coverage trends. | Implemented (Recommended) |
| **Arize Phoenix** | LLM Eval / Observability | Hallucination, relevance, and groundedness eval scoring on LLM outputs. | Implemented (Primary) |
| **Langfuse** | LLM Observability | Scored evals, dataset runs, and prompt-version validation per trace. | Implemented (Primary) |
| **MLflow** | Model Registry / MLOps | Model lineage, prompt version coverage, and audit-evidence tracking. | Implemented (Candidate) |
| **SigNoz** | APM | End-to-end trace validation and integration-test span analysis. | Candidate |
| **OpenObserve** | Observability Platform | Validation log aggregation and assertion-result queries. | Optional |
| **Jaeger** | Distributed Tracing | Trace completeness for end-to-end integration validation. | Optional |
| **Uptrace** | APM | OTel span validation and error-rate verification. | Optional |
| **Apache SkyWalking** | APM | Service path validation and dependency-trace checks. | Optional |
| **Helicone** | LLM Gateway / Proxy | Request/response logging for output-schema and policy checks. | Optional |
| **Elastic APM** | APM | Transaction validation metrics. | Optional |
| **OpenMeter** | Metering | Cost validation only. | Not Implemented |

---

## 2. Validation Parameters Supported

### Required Components
* **Definition:** The total number of system components, guardrails, and compliance checks requested for an agent validation run.
* **Formula:** `Sum(Total defined compliance checks)`
* **Source Resource:** OpenTelemetry / Backend Engine
* **Backend Source:** `api/scoring.py` (`required_components`)
* **Database Source:** `AgentObservation.validation.required_components` (JSON `V` dict)
* **Dashboard Source:** DPI-LS Dashboard "Validation Compliance" / Prometheus `required_components_gauge`.

### Validated Components
* **Definition:** The number of system components that successfully passed all programmatic compliance checks and validation assertions.
* **Formula:** `Sum(Passed compliance checks)`
* **Source Resource:** OpenTelemetry / Backend Engine
* **Backend Source:** `api/scoring.py` (`validated_components`)
* **Database Source:** `AgentObservation.validation.validated_components` (JSON `V` dict)
* **Dashboard Source:** DPI-LS Dashboard "Validation Compliance" / Prometheus `validated_components_gauge`.

### Validation Score
* **Definition:** The overall pass rate of the required technical components and behavioral bounds for the agent.
* **Formula:** `Validated Components / Required Components`
* **Source Resource:** DPI-LS Metric Engine
* **Backend Source:** `api/scoring.py`
* **Database Source:** Calculated live during scoring; persisted in telemetry payload.
* **Dashboard Source:** Prometheus (`validation_score` Gauge).

### Compliance Score
* **Definition:** A weighted roll-up metric reflecting how strictly the agent adhered to policy, data privacy, and prompt guardrails.
* **Formula:** Derived from `AgentObservation.policy` and `validation_score`.
* **Source Resource:** DPI-LS Metric Engine
* **Backend Source:** `engine/rating.py`
* **Database Source:** `AgentObservation.policy` block.
* **Dashboard Source:** DPI-LS Web Dashboard.
