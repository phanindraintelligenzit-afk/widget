# DPI-LS — Quality Resource Data Sources
**Final Presentation Version**

## 1. Resource Catalogue Integration (Quality focus)

| Resource Name | Category | Purpose | Implementation Status |
|---|---|---|---|
| **Arize Phoenix** | LLM Observability | Hallucination detection, relevance scoring, and embedding drift. | Implemented (Primary) |
| **Langfuse** | LLM Observability | Evaluator routing, dataset testing, and prompt versioning evals. | Implemented (Primary) |
| **OpenTelemetry (OTel)** | Instrumentation Standard | Core telemetry standard exporting the Q dictionary payload to backends. | Implemented (Foundational) |
| **Prometheus** | Metrics Store | Time-series aggregations for model degradation and quality alerts. | Implemented (Recommended) |
| **Grafana** | Metrics Visualization | Dashboarding of Hallucination rates, Quality scores over time. | Implemented (Recommended) |
| **MLflow** | MLOps Registry | Tracking evaluator LLM parameters and Quality outcomes per run. | Implemented (Candidate) |
| **OpenObserve** | Observability Platform | Visual log analytics across quality assertions and traces. | Optional |
| **Jaeger** | Distributed Tracing | Span visualization for context retrieval paths. | Optional |
| **Uptrace** | APM | Trace inspection for context injection failure nodes. | Optional |
| **SigNoz** | APM | Error-rate aggregation for quality-impacting traces. | Candidate |

---

## 2. Quality Parameters Supported

### Groundedness
* **Definition:** The degree to which the LLM's generated response is supported entirely by the retrieved context, without introducing external unsourced facts.
* **Formula:** LLM-as-a-judge score (0.0 to 1.0) evaluating Context vs. Response.
* **Source Resource:** Arize Phoenix
* **Backend Source:** `api/scoring.py` (`groundedness_score`)
* **Database Source:** `AgentObservation.quality.groundedness_score` (JSON `Q` dict)
* **Dashboard Source:** DPI-LS Dashboard / Prometheus `groundedness_score_gauge`.

### Hallucination
* **Definition:** The rate at which the LLM generates information that contradicts the source context or invents factual statements.
* **Formula:** LLM-as-a-judge score (0.0 to 1.0) — **Lower is better.**
* **Source Resource:** Arize Phoenix
* **Backend Source:** `api/scoring.py` (`hallucination_score`)
* **Database Source:** `AgentObservation.quality.hallucination_rate`
* **Dashboard Source:** DPI-LS Dashboard / Prometheus `hallucination_score_gauge`.

### Relevance
* **Definition:** How well the LLM's response directly addresses the user's initial query or instruction.
* **Formula:** LLM-as-a-judge score (0.0 to 1.0).
* **Source Resource:** Arize Phoenix
* **Backend Source:** `api/scoring.py` (`relevance_score`)
* **Database Source:** `AgentObservation.quality.relevance_score`
* **Dashboard Source:** Prometheus `relevance_score_gauge`.

### Model Correctness
* **Definition:** An aggregate proxy for QA accuracy, measuring if the model output matched the expected ground-truth dataset in regression testing.
* **Formula:** `Pass / Total Test Cases`
* **Source Resource:** Langfuse / MLflow
* **Backend Source:** `api/scoring.py` (`qa_accuracy_score`)
* **Database Source:** `AgentObservation.quality.accuracy`
* **Dashboard Source:** Prometheus `qa_accuracy_gauge`.

### User Feedback
* **Definition:** Explicit human-in-the-loop scoring (thumbs up/down or 1-5 rating) on the agent's output.
* **Formula:** Normalized numeric rating.
* **Source Resource:** Langfuse
* **Backend Source:** `api/scoring.py` (`user_feedback_score`)
* **Database Source:** `AgentObservation.quality.user_feedback`
* **Dashboard Source:** Prometheus `user_feedback_gauge`.

### Quality Score
* **Definition:** The DPI-LS proprietary composite score blending correctness, consistency, and hallucination penalization.
* **Formula:** `(Accuracy * 0.7) + (Consistency * 0.3) * (1 - Hallucination Rate * 0.1)`
* **Source Resource:** DPI-LS Metric Engine
* **Backend Source:** `engine/rating.py`
* **Database Source:** Stored as part of the `Rating` object in `score_history`.
* **Dashboard Source:** DPI-LS Dashboard.
