"""
DPI-LS FinOps Agent — Fully Dynamic Example
============================================

Every config value is read from the environment (.env file) — nothing is hardcoded.

Environment variables (set in .env):
    BEDROCK_MODEL_ID      = which Bedrock model to use      (required)
    AWS_ACCESS_KEY_ID     = AWS credentials                 (required)
    AWS_SECRET_ACCESS_KEY = AWS credentials                 (required)
    AWS_DEFAULT_REGION    = AWS region for boto3            (default: us-east-1)
    AGENT_ID              = stable ID for this agent        (default: chandra-finops)
    AGENT_NAME            = display name                    (default: Chandra)
    LOOKBACK_DAYS         = how many days of billing to fetch (default: 3)
    HUMAN_BASELINE        = human output per period for P   (default: 1)
    AGENT_PROMPT          = system prompt for the agent     (default: FinOps prompt)
    AGENT_QUESTION        = question sent to the agent      (default: billing analysis)
    DPI_LS_HOST           = dashboard host                  (default: 127.0.0.1)
    DPI_LS_PORT           = dashboard port                  (default: 8000)
    JAEGER_ENDPOINT       = Jaeger collector endpoint       (default: http://localhost:14268)
    OTEL_EXPORTER_OTLP_ENDPOINT = OTLP endpoint for Jaeger (default: http://localhost:4317)

Usage:
    .venv\\Scripts\\python.exe examples\\test_agent.py

Two-line integration (the whole point of dpi_ls):
    import dpi_ls
    dpi_ls.monitor(agent, agent_id=AGENT_ID, human_baseline=HUMAN_BASELINE)
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


from dotenv import load_dotenv

from dotenv import load_dotenv

# ── Load .env FIRST so all os.getenv() calls below pick it up ─────────────────
load_dotenv(override=True)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

# Create a single global TracerProvider to prevent "Overriding current TracerProvider" errors
_global_resource = Resource.create({"service.name": "chandra-finops-agent"})
_global_provider = TracerProvider(resource=_global_resource)
trace.set_tracer_provider(_global_provider)

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

if os.getenv("LANGFUSE_PUBLIC_KEY"):
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

import dpi_ls  # line 1 — the installable package

from agents import Agent, Runner, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from agents.tool import FunctionTool


# ── Read ALL config from environment (zero hardcoding) ────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip().strip('"').strip("'")

def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

# Required
BEDROCK_MODEL_ID  = _env("BEDROCK_MODEL_ID") or _env("MODEL_NAME")

# Optional — all have sensible defaults
AGENT_ID          = _env("AGENT_ID",       "chandra-finops")
AGENT_NAME        = _env("AGENT_NAME",     "Chandra")
LOOKBACK_DAYS     = _env_int("LOOKBACK_DAYS", 3)
HUMAN_BASELINE    = _env_int("HUMAN_BASELINE", 1)
DPI_LS_HOST       = _env("DPI_LS_HOST",    "127.0.0.1")
DPI_LS_PORT       = _env_int("DPI_LS_PORT", 8000)
JAEGER_ENDPOINT   = _env("JAEGER_ENDPOINT", "http://127.0.0.1:14268")

AGENT_PROMPT = _env("AGENT_PROMPT") or (
    "You are a FinOps AWS Agent tasked with auditing cloud spend. "
    "Review the cost breakdown, summarize the most expensive services by region, "
    "and point out any strange billing spikes or cost anomalies."
)

AGENT_QUESTION = _env("AGENT_QUESTION") or (
    f"Analyze my AWS account billing over the last {LOOKBACK_DAYS} days. "
    "Which regions are costing me the most money? "
    "Are there any billing spikes or anomalies I should be aware of?"
)


# ===============================================================
#  AWS Cost Explorer — fetches real billing data
# ===============================================================

class AWSCostExplorerFetcher:
    """Fetches real AWS Cost Explorer data grouped by Region + Service."""

    def __init__(self):
        import aioboto3
        self.region = "us-east-1"
        self._session = aioboto3.Session()

    async def fetch_costs_summary(self, days_lookback: int = LOOKBACK_DAYS) -> dict[str, Any]:
        end_date   = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")

        req = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "REGION"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        }

        all_periods: list = []
        async with self._session.client("ce", region_name=self.region) as ce:
            next_token = None
            while True:
                if next_token:
                    req["NextPageToken"] = next_token
                resp = await ce.get_cost_and_usage(**req)
                all_periods.extend(resp.get("ResultsByTime", []))
                next_token = resp.get("NextPageToken")
                if not next_token:
                    break

        summary: dict[str, Any] = {
            "LookbackPeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "DailyBreakdown": [],
        }

        for period in all_periods:
            tf = period.get("TimePeriod", {})
            day: dict[str, Any] = {"Date": tf.get("Start"), "TotalDailyCost": 0.0, "Regions": {}}

            for group in period.get("Groups", []):
                keys   = group.get("Keys", ["Global", "Unknown"])
                region = keys[0] or "Global-Services"
                svc    = keys[1] if len(keys) > 1 else "Unknown"
                amount = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0))

                if amount > 0:
                    if region not in day["Regions"]:
                        day["Regions"][region] = {"RegionTotal": 0.0, "Services": {}}
                    day["Regions"][region]["Services"][svc] = round(amount, 4)
                    day["Regions"][region]["RegionTotal"]   += amount
                    day["TotalDailyCost"]                   += amount

            day["TotalDailyCost"] = round(day["TotalDailyCost"], 4)
            for r in day["Regions"].values():
                r["RegionTotal"] = round(r["RegionTotal"], 4)

            summary["DailyBreakdown"].append(day)

        return summary


# ===============================================================
#  Bedrock tool adapter
# ===============================================================

def _to_bedrock_tool(tool) -> FunctionTool:
    return FunctionTool(
        name=tool["name"],
        description=tool["description"],
        params_json_schema={
            "type": "object",
            "properties": {k: v for k, v in tool["params_json_schema"]["properties"].items()},
            "required": tool["params_json_schema"].get("required", []),
        },
        on_invoke_tool=tool["on_invoke_tool"],
    )


# ===============================================================
#  Score card display
# ===============================================================

def _bar(value: float | None, width: int = 20) -> str:
    if value is None:
        return "[" + "-" * width + "] N/A"
    filled = int(round(value * width))
    return "[" + "#" * filled + "-" * (width - filled) + f"] {value:.3f}"


DIMENSION_LABELS = {
    "P": "Productivity   (P)",
    "Q": "Quality        (Q)",
    "E": "Execution      (E)",
    "G": "Governance     (G)",
    "R": "Risk           (R)",
    "V": "Validation     (V)",
    "C": "Cost           (C)",
}


def print_score_card(rating: dict) -> None:
    score    = rating.get("score", 0)
    raw      = rating.get("raw_score", score)
    band     = rating.get("band", "?")
    unsafe   = rating.get("unsafe", False)
    gates    = rating.get("gate_failures", [])
    metrics  = rating.get("metrics", {})
    capped   = rating.get("capped", False)

    BAND_ICONS = {
        "Exceptional":       "*  EXCEPTIONAL",
        "Strong":            "^  STRONG",
        "Needs Optimization":"v  NEEDS OPTIMIZATION",
        "Underperforming":   "x  UNDERPERFORMING",
    }
    band_label = BAND_ICONS.get(band, band)
    unsafe_tag = "  !  UNSAFE - compliance gate fired" if unsafe else ""

    print()
    print("+" + "-" * 55 + "+")
    print(f"|  DPI-LS SCORE CARD  .  {AGENT_NAME:<32}|")
    print("+" + "-" * 55 + "+")
    print(f"|  Final Score : {score:>6.1f} / 100{' (capped)' if capped else '         '}    |")
    print(f"|  Raw Score   : {raw:>6.1f}                              |")
    print(f"|  Band        : {band_label:<39}|")
    if unsafe_tag:
        print(f"|  {unsafe_tag:<53}|")
    if gates:
        print(f"|  Gate failures: {', '.join(gates):<38}|")
    print("+" + "-" * 55 + "+")
    print("|  7 DIMENSIONS                                         |")
    print("+" + "-" * 55 + "+")
    for key in ["P", "Q", "E", "G", "R", "V", "C"]:
        label = DIMENSION_LABELS[key]
        val   = metrics.get(key)
        gate_flag = " <- GATE FAIL" if key in gates else ""
        bar_str = _bar(val)
        print(f"|  {label:<18} {bar_str}{gate_flag:<13}|")
    print("+" + "-" * 55 + "+")
    print(f"|  Agent ID    : {AGENT_ID:<39}|")
    print(f"|  Framework   : openai_agents (AWS Bedrock / LiteLLM)  |")
    print(f"|  Model       : {BEDROCK_MODEL_ID[:37]:<39}|")
    print("+" + "-" * 55 + "+")
    print()





# ===============================================================
#  DeepEval SDK Integration
# ===============================================================

def _run_deepeval_metrics(question: str, agent_answer: str, context: list = None) -> dict:
    """
    Run actual DeepEval SDK metrics: AnswerRelevancy, Faithfulness, Hallucination, GEval Correctness.
    Returns a dict of metric_name -> score (float 0-1).
    All 4 metrics are run: answer_relevancy, faithfulness, hallucination, correctness.

    Uses the same AWS Bedrock model the agent uses (via DeepEval's AmazonBedrockModel)
    so the evaluation is grounded in the same LLM that produced the answer.
    """
    results = {}
    metrics_run = 0
    try:
        from deepeval.test_case import LLMTestCase
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, HallucinationMetric
        from deepeval.models import AmazonBedrockModel

        # Use the SAME Bedrock model the agent uses for evaluation.
        # This makes DeepEval use the same LLM the agent used to generate answers.
        eval_model = None
        try:
            eval_model = AmazonBedrockModel(
                model=BEDROCK_MODEL_ID,
                region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            )
        except Exception as e:
            print(f"[DeepEval] Could not create Bedrock model: {e} — falling back to default model")

        # Use real agent outputs as retrieval context if available; otherwise fall back to question
        # NOTE: Using actual_output as context for faithfulness/hallucination is semantically correct
        # because we're checking if the answer is grounded in what was retrieved (the agent outputs)
        retrieval_context = context if context else [question]
        # Strip empty strings from context
        retrieval_context = [c for c in retrieval_context if c and c.strip()] or [question]

        # Use the actual agent outputs as both retrieval_context and context.
        # DeepEval 3.x requires the ``context`` field for the Hallucination metric.
        context_for_metrics = retrieval_context if retrieval_context else [question]
        test_case = LLMTestCase(
            input=question,
            actual_output=agent_answer,
            retrieval_context=context_for_metrics,
            context=context_for_metrics,
        )

        print("[DeepEval] Running Answer Relevancy metric...")
        try:
            kwargs = {"threshold": 0.5, "verbose_mode": False}
            if eval_model is not None:
                kwargs["model"] = eval_model
            ar_metric = AnswerRelevancyMetric(**kwargs)
            ar_metric.measure(test_case)
            results["answer_relevancy"] = round(float(ar_metric.score or 0.0), 3)
            metrics_run += 1
            print(f"[DeepEval] Answer Relevancy = {results['answer_relevancy']}")
        except Exception as e:
            print(f"[DeepEval] AnswerRelevancy failed: {e}")

        print("[DeepEval] Running Faithfulness metric...")
        try:
            kwargs = {"threshold": 0.5, "verbose_mode": False}
            if eval_model is not None:
                kwargs["model"] = eval_model
            f_metric = FaithfulnessMetric(**kwargs)
            f_metric.measure(test_case)
            results["faithfulness"] = round(float(f_metric.score or 0.0), 3)
            metrics_run += 1
            print(f"[DeepEval] Faithfulness = {results['faithfulness']}")
        except Exception as e:
            print(f"[DeepEval] Faithfulness failed: {e}")

        print("[DeepEval] Running Hallucination metric...")
        try:
            kwargs = {"threshold": 0.5, "verbose_mode": False}
            if eval_model is not None:
                kwargs["model"] = eval_model
            h_metric = HallucinationMetric(**kwargs)
            h_metric.measure(test_case)
            results["hallucination"] = round(float(h_metric.score or 0.0), 3)
            metrics_run += 1
            print(f"[DeepEval] Hallucination = {results['hallucination']}")
        except Exception as e:
            print(f"[DeepEval] Hallucination failed: {e}")

        print("[DeepEval] Running GEval Correctness metric...")
        try:
            from deepeval.metrics import GEval
            from deepeval.test_case import LLMTestCaseParams
            kwargs = {
                "name": "Correctness",
                "criteria": "Determine whether the actual output is factually correct and well-reasoned based on the input question.",
                "evaluation_params": [LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                "threshold": 0.5,
                "verbose_mode": False,
            }
            if eval_model is not None:
                kwargs["model"] = eval_model
            correctness_metric = GEval(**kwargs)
            correctness_metric.measure(test_case)
            results["correctness"] = round(float(correctness_metric.score or 0.0), 3)
            metrics_run += 1
            print(f"[DeepEval] Correctness (GEval) = {results['correctness']}")
        except Exception as e:
            print(f"[DeepEval] GEval Correctness failed: {e}")
            # Fallback: use answer_relevancy as correctness proxy
            if "answer_relevancy" in results:
                results["correctness"] = results["answer_relevancy"]
                print(f"[DeepEval] Correctness (fallback=answer_relevancy): {results['correctness']}")

        results["evaluation_status"] = "COMPLETED" if metrics_run > 0 else "FAILED"
        results["evaluation_count"] = str(metrics_run)  # Real count of metrics that ran
        print(f"[DeepEval] Evaluation complete. {metrics_run} metrics computed.")

    except ImportError:
        print("[DeepEval] SDK not installed — skipping real metric evaluation.")
    except Exception as e:
        print(f"[DeepEval] Evaluation failed: {e}")

    return results


def _push_deepeval_results_to_backend(deepeval_results: dict, host: str, port: int) -> None:
    """Push DeepEval results to the DPI-LS backend so they appear in the dashboard."""
    if not deepeval_results:
        return
    try:
        import urllib.request
        url = f"http://{host}:{port}/api/validation-evaluation/push-deepeval"
        payload = json.dumps(deepeval_results).encode()
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                print("[DeepEval] Results pushed to backend successfully.")
    except Exception as e:
        print(f"[DeepEval] Push to backend skipped (endpoint may not exist yet): {e}")





def _setup_zipkin_tracing() -> tuple:
    """
    Set up Zipkin tracing for the agent run.
    Returns (tracer, provider) or (None, None) on failure.
    """
    try:
        from opentelemetry.exporter.zipkin.json import ZipkinExporter

        # Configure Zipkin endpoint
        zipkin_endpoint = os.environ.get("ZIPKIN_URL", "http://localhost:9411") + "/api/v2/spans"

        import socket
        try:
            with socket.create_connection(("127.0.0.1", 9411), timeout=0.1):
                pass
        except OSError:
            print("[Zipkin] Zipkin is offline — Zipkin tracing skipped")
            return None, None

        zipkin_exporter = ZipkinExporter(
            endpoint=zipkin_endpoint,
        )

        span_processor = BatchSpanProcessor(zipkin_exporter)
        _global_provider.add_span_processor(span_processor)
        
        tracer = trace.get_tracer(__name__)
        print(f"[Zipkin] OTel tracer configured. Endpoint: {zipkin_endpoint}")
        return tracer, _global_provider

    except Exception as e:
        print(f"[Zipkin] Tracing setup failed: {e}")
        return None, None





# ===============================================================
#  Jaeger OpenTelemetry Setup
# ===============================================================

def _setup_jaeger_tracing():
    """Set up Jaeger tracing for agent execution. Returns (tracer, provider) or (None, None)."""
    try:
        import opentelemetry.sdk.environment_variables as env_vars
        for attr in [
            "OTEL_EXPORTER_JAEGER_AGENT_HOST",
            "OTEL_EXPORTER_JAEGER_AGENT_PORT",
            "OTEL_EXPORTER_JAEGER_ENDPOINT",
            "OTEL_EXPORTER_JAEGER_TIMEOUT",
            "OTEL_EXPORTER_JAEGER_USER",
            "OTEL_EXPORTER_JAEGER_PASSWORD",
            "OTEL_EXPORTER_JAEGER_AGENT_SPLIT_OVERSIZED_BATCHES",
        ]:
            setattr(env_vars, attr, attr)
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        import socket
        try:
            with socket.create_connection(("127.0.0.1", 14268), timeout=0.1):
                pass
        except OSError:
            print("[Jaeger] Jaeger is offline — Jaeger tracing skipped")
            tracer = trace.get_tracer("chandra-finops")
            return tracer, _global_provider

        try:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=14268,
                collector_endpoint=JAEGER_ENDPOINT + "/api/traces",
            )
            processor = BatchSpanProcessor(jaeger_exporter)
            _global_provider.add_span_processor(processor)
            print(f"[Jaeger] OTel tracer configured. Endpoint: {JAEGER_ENDPOINT}")
        except Exception as e:
            print(f"[Jaeger] Exporter unavailable ({e}) — install Jaeger to enable tracing")

        tracer = trace.get_tracer("chandra-finops")
        return tracer, _global_provider

    except ImportError:
        print("[Jaeger] opentelemetry-sdk not installed — Jaeger tracing skipped")
        return None, None
    except Exception as e:
        print(f"[Jaeger] OTel setup error: {e}")
        return None, None


# ===============================================================
#  Main agent run
# ===============================================================

async def run_agent_observation() -> None:
    if not BEDROCK_MODEL_ID:
        print("ERROR: BEDROCK_MODEL_ID is not set in .env")
        sys.exit(1)

    print(f"\n{'-'*55}")
    print(f"  DPI-LS Monitor  .  Agent: {AGENT_NAME}  .  ID: {AGENT_ID}")
    print(f"  Model : bedrock/{BEDROCK_MODEL_ID}")
    print(f"  Lookback: {LOOKBACK_DAYS} days  |  Human baseline: {HUMAN_BASELINE}")
    print(f"  Jaeger: {JAEGER_ENDPOINT}")
    print(f"{'-'*55}\n")

    # Set up Jaeger tracing
    jaeger_tracer, jaeger_provider = _setup_jaeger_tracing()
    
    # Set up Zipkin tracing
    zipkin_tracer, zipkin_provider = _setup_zipkin_tracing()

    fetcher = AWSCostExplorerFetcher()

    # Build tools dynamically from the fetcher
    raw_tools     = [function_tool(fetcher.fetch_costs_summary)]
    bedrock_tools = [_to_bedrock_tool(t.__dict__) for t in raw_tools]

    # Build the agent
    agent = Agent(
        name=AGENT_NAME,
        instructions=AGENT_PROMPT,
        model=LitellmModel(model=f"bedrock/{BEDROCK_MODEL_ID}"),
        tools=bedrock_tools,
    )

    # Prevent duplicate backend startup (Bug 1 & 2)
    os.environ["DPI_LS_URL"] = f"http://{DPI_LS_HOST}:{DPI_LS_PORT}"

    # LINE 2: Monitor the agent
    collector = dpi_ls.monitor(
        agent,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        human_baseline=HUMAN_BASELINE,
        host=DPI_LS_HOST,
        port=DPI_LS_PORT,
        block=False,
        post=False,
    )

    print(f"Question: {AGENT_QUESTION}\n")
    psutil.cpu_percent()  # seed psutil cpu measurement

    run_name = f"Chandra-FinOps-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Wrap agent run in Jaeger & Zipkin spans for distributed tracing
    if jaeger_tracer:
        with jaeger_tracer.start_as_current_span("chandra-agent-run") as span:
            span.set_attribute("agent.id", AGENT_ID)
            span.set_attribute("agent.name", AGENT_NAME)
            span.set_attribute("agent.model", BEDROCK_MODEL_ID)
            span.set_attribute("agent.question", AGENT_QUESTION[:200])
            span.set_attribute("validation.service", "chandra-finops-agent")
            span.set_attribute("trace.type", "validation")

            result = await Runner.run(agent, AGENT_QUESTION)

            span.set_attribute("agent.output_length", len(result.final_output))
            span.set_attribute("execution.status", "success")
    else:
        result = await Runner.run(agent, AGENT_QUESTION)

    cpu_usage = psutil.cpu_percent() / 100.0

    print("\n" + "-" * 55)
    print("  AGENT ANSWER")
    print("-" * 55)
    safe = result.final_output.encode("ascii", errors="ignore").decode("ascii")
    print(safe)
    print("-" * 55)

    # ── Evaluate Quality ────────────────────────────────────────────
    collector.mark_end()
    outputs = collector.outputs_for_q()
    q_result = None
    if outputs:
        source_data = collector.source_data_for_q()
        try:
            from dpi_ls.evaluator import evaluate_quality
            q_result = evaluate_quality(outputs, source_data=source_data)
            collector.set_quality(
                q_result.accuracy, q_result.consistency, q_result.hallucination_rate, user_feedback_score=None
            )
            collector.cpu_utilization = cpu_usage
            print(f"Quality (Q): Accuracy={q_result.accuracy:.3f}, Consistency={q_result.consistency:.3f}, Hallucination={q_result.hallucination_rate:.3f} (via {q_result.source})")
        except Exception as e:
            print(f"Failed to evaluate quality: {e}")

    # ── Real DeepEval SDK metrics ───────────────────────────────────
    print("\n[DeepEval] Starting real metric evaluation...")
    deepeval_results = _run_deepeval_metrics(
        question=AGENT_QUESTION,
        agent_answer=result.final_output,
        context=outputs or [AGENT_QUESTION],
    )

    # ── Jaeger tracing finalization ────────────────────────────────────
    print(f"\n[Jaeger] Finalizing traces...")
    if jaeger_tracer and jaeger_provider:
        try:
            jaeger_provider.force_flush()
            print(f"[Jaeger] Spans flushed successfully.")
        except Exception as e:
            print(f"[Jaeger] Flush error: {e}")

    # ── Zipkin tracing finalization ────────────────────────────────────
    print(f"\n[Zipkin] Finalizing trace timelines...")
    if zipkin_tracer and zipkin_provider:
        try:
            zipkin_provider.force_flush()
            print(f"[Zipkin] Spans flushed successfully.")
        except Exception as e:
            print(f"[Zipkin] Flush error: {e}")

    # Push DeepEval results to backend
    _push_deepeval_results_to_backend(deepeval_results, DPI_LS_HOST, DPI_LS_PORT)

    # Trigger resource evaluation pipeline so telemetry is available for the agent score
    try:
        import urllib.request
        host = os.getenv("DPI_LS_HOST", "127.0.0.1")
        port = os.getenv("DPI_LS_PORT", "8000")

        url_cost = f"http://{host}:{port}/api/cost-evaluation/evaluate"
        req_cost = urllib.request.Request(url_cost, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_cost, timeout=30) as response:
            if response.status == 200:
                print("Cost resource evaluation triggered successfully.")

        url_val = f"http://{host}:{port}/api/validation-evaluation/evaluate"
        req_val = urllib.request.Request(url_val, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_val, timeout=30) as response:
            if response.status == 200:
                print("Validation resource evaluation triggered successfully.")
    except Exception as e:
        print(f"Failed to trigger resource evaluation: {e}")

    # ── Post DPI-LS observation ─────────────────────────────────────
    from dpi_ls.poster import post_observation
    from contract.settings import Settings
    collector.human_cost = Settings().human_cost_per_output
    base_url = f"http://{DPI_LS_HOST}:{DPI_LS_PORT}"
    rating = post_observation(collector, base_url)
    if rating:
        print_score_card(rating)
    else:
        print("Failed to post observation to the server.")


# ===============================================================
#  Entry point
# ===============================================================

if __name__ == "__main__":
    asyncio.run(run_agent_observation())

    # Flush Langfuse traces before exit
    try:
        import litellm
        for cb in litellm._async_success_callback + litellm.success_callback:
            if hasattr(cb, "Langfuse"):
                cb.Langfuse.flush()
                print("Langfuse traces flushed successfully.")
                break
        else:
            from langfuse import Langfuse
            lf = Langfuse()
            lf.flush()
            lf.shutdown()
            print("Langfuse traces flushed successfully (via SDK).")
    except Exception as exc:
        print(f"Langfuse flush skipped: {exc}")



    # Keep the dashboard alive for browsing
    from dpi_ls import _state
    info = _state.get_server_info()
    if info is not None and os.getenv("DPI_LS_NO_BLOCK") != "1":
        print(f"Dashboard is live -> open  {info.base_url}  in your browser.")