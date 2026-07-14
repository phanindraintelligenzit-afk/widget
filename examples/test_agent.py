"""
DPI-LS FinOps Agent ΓÇö Fully Dynamic Example
============================================

Every config value is read from the environment (.env file) ΓÇö nothing is hardcoded.

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

# ΓöÇΓöÇ Load .env FIRST so all os.getenv() calls below pick it up ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
load_dotenv(override=True)

if os.getenv("AGENTOPS_API_KEY"):
    import agentops
    agentops.init(os.getenv("AGENTOPS_API_KEY"))

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

if os.getenv("LANGFUSE_PUBLIC_KEY"):
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

import dpi_ls  # line 1 ΓÇö the installable package

from agents import Agent, function_tool, Runner
from agents.extensions.models.litellm_model import LitellmModel
from agents.tool import FunctionTool


# ΓöÇΓöÇ Read ALL config from environment (zero hardcoding) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip().strip('"').strip("'")

def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

# Required
BEDROCK_MODEL_ID  = _env("BEDROCK_MODEL_ID") or _env("MODEL_NAME")

# Optional ΓÇö all have sensible defaults
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


# ===============================================================
#  AWS Cost Explorer ΓÇö fetches real billing data
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
    print(f"{'-'*55}\n")

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
    )

    # Store the input query for telemetry
    collector.record_source(AGENT_QUESTION, kind="input")

    print(f"Question: {AGENT_QUESTION}\n")

    # Start CPU measuring
    psutil.cpu_percent()

    result = await Runner.run(agent, AGENT_QUESTION)

    collector.cpu_utilization = psutil.cpu_percent() / 100.0
    
    # Run the SDK evaluations synchronously before script exit to avoid ThreadPool errors in atexit
    collector.finalize()

    print("\n" + "-" * 55)
    print("  AGENT ANSWER")
    print("-" * 55)
    safe = result.final_output.encode("ascii", errors="ignore").decode("ascii")
    print(safe)
    print("-" * 55)


# ===============================================================
#  Entry point
# ===============================================================

if __name__ == "__main__":
    asyncio.run(run_agent_observation())
