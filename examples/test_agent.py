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

Usage:
    .venv\\Scripts\\python.exe examples\\test_agent.py

Two-line integration (the whole point of dpi_ls):
    import dpi_ls
    dpi_ls.monitor(agent, agent_id=AGENT_ID, human_baseline=HUMAN_BASELINE)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Fix Windows terminal emoji printing crash
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# ── Load .env FIRST so all os.getenv() calls below pick it up ─────────────────
load_dotenv(override=True)

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


# ═══════════════════════════════════════════════════════════════════
#  AWS Cost Explorer — fetches real billing data from your account
# ═══════════════════════════════════════════════════════════════════

class AWSCostExplorerFetcher:
    """Fetches real AWS Cost Explorer data grouped by Region + Service."""

    def __init__(self):
        import aioboto3
        # CE is a global endpoint — always us-east-1
        self.region = "us-east-1"
        self._session = aioboto3.Session()

    async def fetch_costs_summary(self, days_lookback: int = LOOKBACK_DAYS) -> dict[str, Any]:
        """
        Returns a compact daily billing summary by region.
        Filters out $0.00 lines to protect the LLM context window.
        """
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


# ═══════════════════════════════════════════════════════════════════
#  Bedrock tool-schema adapter (OpenAI SDK → Bedrock format)
# ═══════════════════════════════════════════════════════════════════

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


# ===================================================================
#  Score display helpers — shows all 7 dimensions
# ===================================================================

def _bar(value: float | None, width: int = 20) -> str:
    """ASCII progress bar for a [0,1] metric."""
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
    """Print a full DPI-LS score card with all 7 dimensions."""
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


# ===================================================================
#  Main agent run
# ===================================================================

async def run_agent_observation() -> None:
    if not BEDROCK_MODEL_ID:
        print("ERROR: BEDROCK_MODEL_ID is not set in .env")
        sys.exit(1)

    print(f"\n{'-'*55}")
    print(f"  DPI-LS Monitor  .  Agent: {AGENT_NAME}  .  ID: {AGENT_ID}")
    print(f"  Model : bedrock/{BEDROCK_MODEL_ID}")
    print(f"  Lookback: {LOOKBACK_DAYS} days  |  Human baseline: {HUMAN_BASELINE}")
    print(f"{'-'*55}\n")

    fetcher = AWSCostExplorerFetcher()

    # Build tools dynamically from the fetcher
    raw_tools    = [function_tool(fetcher.fetch_costs_summary)]
    bedrock_tools = [_to_bedrock_tool(t.__dict__) for t in raw_tools]

    # -- Build the agent (all config from env) ---------------------
    agent = Agent(
        name=AGENT_NAME,
        instructions=AGENT_PROMPT,
        model=LitellmModel(model=f"bedrock/{BEDROCK_MODEL_ID}"),
        tools=bedrock_tools,
    )

    # -- LINE 2: Monitor the agent ---------------------------------
    collector = dpi_ls.monitor(          # line 2
        agent,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        human_baseline=HUMAN_BASELINE,
        host=DPI_LS_HOST,
        port=DPI_LS_PORT,
        block=False,                     # we handle blocking ourselves below
        post=False,                      # we post explicitly after Q eval
    )

    # -- Run the agent ---------------------------------------------
    print(f"Question: {AGENT_QUESTION}\n")
    psutil.cpu_percent() # Seed the psutil cpu percent measurement
    
    run_name = f"Chandra-FinOps-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    result = await Runner.run(agent, AGENT_QUESTION)
    cpu_usage = psutil.cpu_percent() / 100.0 # Get percentage since last call, convert to 0-1 range

    print("\n" + "-" * 55)
    print("  AGENT ANSWER")
    print("-" * 55)
    # Strip non-ASCII so Windows cp1252 terminals don't crash
    safe = result.final_output.encode("ascii", errors="ignore").decode("ascii")
    print(safe)
    print("-" * 55)

    # ── Evaluate Quality and Post Observation explicitly ───────────
    collector.mark_end()
    outputs = collector.outputs_for_q()
    if outputs:
        source_data = collector.source_data_for_q()
        try:
            from dpi_ls.evaluator import evaluate_quality
            q = evaluate_quality(outputs, source_data=source_data)
            collector.set_quality(
                q.accuracy, q.consistency, q.hallucination_rate, user_feedback_score=None
            )
            collector.cpu_utilization = cpu_usage
            print(f"Evaluated Quality (Q): Accuracy={q.accuracy:.3f}, Consistency={q.consistency:.3f}, Hallucination={q.hallucination_rate:.3f} (via {q.source})")
        except Exception as e:
            print(f"Failed to evaluate quality: {e}")

    # Now post the observation
    from dpi_ls.poster import post_observation
    from contract.settings import Settings
    
    # Dynamically apply the human_cost setting so the payload correctly records it
    collector.human_cost = Settings().human_cost_per_output
    
    base_url = f"http://{DPI_LS_HOST}:{DPI_LS_PORT}"
    rating = post_observation(collector, base_url)
    if rating:
        print_score_card(rating)
    else:
        print("Failed to post observation to the server.")

# ===================================================================
#  Entry point
# ===================================================================

if __name__ == "__main__":
    asyncio.run(run_agent_observation())

    # -- Flush Langfuse traces before exit -----------------------------
    # litellm queues Langfuse events in a background thread.
    # Without an explicit flush, the process exits before traces are sent.
    try:
        import litellm
        for cb in litellm._async_success_callback + litellm.success_callback:
            if hasattr(cb, "Langfuse"):
                cb.Langfuse.flush()
                print("Langfuse traces flushed successfully.")
                break
        else:
            # Fallback: flush via langfuse singleton if litellm didn't expose it
            from langfuse import Langfuse
            lf = Langfuse()
            lf.flush()
            lf.shutdown()
            print("Langfuse traces flushed successfully (via SDK).")
    except Exception as exc:
        print(f"Langfuse flush skipped: {exc}")

    # Automatically trigger the Cost/Validation/Quality resource evaluation pipeline
    try:
        import urllib.request
        import urllib.parse
        host = os.getenv("DPI_LS_HOST", "127.0.0.1")
        port = os.getenv("DPI_LS_PORT", "8000")
        
        # 1. Cost evaluation
        url_cost = f"http://{host}:{port}/api/cost-evaluation/evaluate"
        req_cost = urllib.request.Request(url_cost, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_cost, timeout=30) as response:
            if response.status == 200:
                print("Cost resource evaluation triggered successfully.")
                
        # 2. Validation evaluation
        url_val = f"http://{host}:{port}/api/validation-evaluation/evaluate"
        req_val = urllib.request.Request(url_val, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_val, timeout=30) as response:
            if response.status == 200:
                print("Validation resource evaluation triggered successfully.")
    except Exception as e:
        print(f"Failed to trigger resource evaluation: {e}")

    # Keep the dashboard alive for browsing
    from dpi_ls import _state
    info = _state.get_server_info()
    if info is not None and os.getenv("DPI_LS_NO_BLOCK") != "1":
        print(f"Dashboard is live -> open  {info.base_url}  in your browser.")