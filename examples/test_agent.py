import asyncio
import aioboto3
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
from dotenv import load_dotenv

import dpi_ls                                       # line 1 - installable package

# Framework imports
from agents import Agent, Runner, trace, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from agents.tool import FunctionTool

load_dotenv(override=True)


class AWSCostExplorerFetcher:
    """
    Asynchronously fetches global AWS Cost Explorer data to analyze account spend.

    Requires: pip install aioboto3
    """

    def __init__(self):
        # CE API is a global endpoint. We always communicate with us-east-1.
        self.region = "us-east-1"
        self._session = aioboto3.Session()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def fetch_cost_by_region_and_service(
        self,
        days_lookback: int = 7,
        granularity: str = "DAILY"
    ) -> dict[str, Any]:
        """
        Fetches full, raw AWS cost and usage breakdown globally.
        Groups by REGION first, then by SERVICE.
        """
        # Cost Explorer requires string dates in YYYY-MM-DD
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")

        request_kwargs = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": granularity,
            "Metrics": ["UnblendedCost"],
            # AWS allows a maximum of 2 Dimensions for GroupBy
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "REGION"},
                {"Type": "DIMENSION", "Key": "SERVICE"}
            ],
        }

        all_results_by_time = []
        next_token = None

        # Loop manually to handle pagination for large time windows
        async with self._session.client("ce", region_name=self.region) as ce:
            while True:
                if next_token:
                    request_kwargs["NextPageToken"] = next_token

                response = await ce.get_cost_and_usage(**request_kwargs)
                all_results_by_time.extend(response.get("ResultsByTime", []))

                next_token = response.get("NextPageToken")
                if not next_token:
                    break

        return {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": granularity,
            "ResultsByTime": all_results_by_time
        }

    async def fetch_costs_summary(self, days_lookback: int = 7) -> dict[str, Any]:
        """
        Fetch a compact daily billing summary natively broken down by Region.
        Filters out $0.00 services to protect LLM context windows.
        """
        raw_data = await self.fetch_cost_by_region_and_service(days_lookback=days_lookback)

        summary = {
            "LookbackPeriod": raw_data["TimePeriod"],
            "Granularity": raw_data["Granularity"],
            "DailyBreakdown": []
        }

        for period in raw_data.get("ResultsByTime", []):
            time_frame = period.get("TimePeriod", {})

            daily_record = {
                "Date": time_frame.get("Start"),
                "TotalDailyCost": 0.0,
                "Regions": {}
            }

            for group in period.get("Groups", []):
                # Because we used 2 GroupBy dimensions, Keys will be: [Region, Service]
                keys = group.get("Keys", ["Global", "Unknown"])

                # 'NoRegion' is used by AWS for global services like Route53, IAM, CloudFront, etc.
                region_name = keys[0] if keys[0] else "Global-Services"
                service_name = keys[1] if len(keys) > 1 else "Unknown"

                metrics = group.get("Metrics", {})
                unblended = metrics.get("UnblendedCost", {})

                amount = float(unblended.get("Amount", 0))

                # Filter out negligible costs (<= $0.00)
                if amount > 0:
                    # Initialize the region dict if it doesn't exist yet
                    if region_name not in daily_record["Regions"]:
                        daily_record["Regions"][region_name] = {"RegionTotal": 0.0, "Services": {}}

                    # Add to the region's service breakdown
                    daily_record["Regions"][region_name]["Services"][service_name] = round(amount, 4)

                    # Add to the rolling totals
                    daily_record["Regions"][region_name]["RegionTotal"] += amount
                    daily_record["TotalDailyCost"] += amount

            # Round the totals so they render cleanly in JSON
            daily_record["TotalDailyCost"] = round(daily_record["TotalDailyCost"], 4)
            for reg in daily_record["Regions"].values():
                reg["RegionTotal"] = round(reg["RegionTotal"], 4)

            summary["DailyBreakdown"].append(daily_record)

        return summary


# ================================================================== #
#  Tool schema adapter: OpenAI -> Bedrock                            #
# ================================================================== #

def _convert_tool_for_bedrock(tool) -> FunctionTool:
    """
    Bedrock's tool-use schema differs from OpenAI's.
    This adapter re-wraps each FunctionTool so the Agents SDK sends
    the correct schema format to the Bedrock API.

    Ref: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html
    """
    return FunctionTool(
        name=tool["name"],
        description=tool["description"],
        params_json_schema={
            "type": "object",
            "properties": {
                k: v for k, v in tool["params_json_schema"]["properties"].items()
            },
            "required": tool["params_json_schema"].get("required", []),
        },
        on_invoke_tool=tool["on_invoke_tool"],
    )


# ================================================================== #
#  Execution and Agent integration                                   #
# ================================================================== #

async def main():
    fetcher = AWSCostExplorerFetcher()

    # 1. Export comprehensive raw billing data locally
    report = await fetcher.fetch_costs_summary(days_lookback=3)
    output_path = Path("observation") / "cost_explorer_raw.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=4), encoding="utf-8")
    print(f"Successfully written full raw billing report to {output_path}")

    # Print the clean summary to the terminal so you can see the new structure
    summary = await fetcher.fetch_costs_summary(days_lookback=3)
    print(json.dumps(summary, indent=4))


async def run_agent_observation() -> None:
    # -----------------------------------------------------------------
    # Load Bedrock model ID from .env
    #   BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
    #   BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
    #   BEDROCK_MODEL_ID=us.meta.llama3-3-70b-instruct-v1:0
    # AWS credentials are resolved automatically by boto3 from the
    # environment (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY /
    # AWS_DEFAULT_REGION) or from an active IAM role / SSO session.
    # -----------------------------------------------------------------
    bedrock_model_id = os.environ["BEDROCK_MODEL_ID"]

    fetcher = AWSCostExplorerFetcher()

    # Build raw function tools, then convert each one to Bedrock schema
    raw_tools = [function_tool(fetcher.fetch_costs_summary)]
    bedrock_tools = [_convert_tool_for_bedrock(t.__dict__) for t in raw_tools]

    prompt = (
        "You are a FinOps AWS Agent tasked with auditing cloud spend. "
        "Review the cost breakdown, summarize the most expensive services by region, "
        "and point out any strange billing spikes."
    )

    agent = Agent(
        name="Chandra",
        instructions=prompt,
        # LiteLLM routes "bedrock/<model_id>" -> AWS Bedrock automatically.
        # The "litellm/" prefix tells the Agents SDK to use LitellmModel routing.
        model=LitellmModel(model=f"bedrock/{bedrock_model_id}"),
        tools=bedrock_tools,
    )

    # human_baseline=1: Chandra produces 1 analysis report per run,
    # matching one human analyst who would produce the same 1 report.
    # Without this, P defaults to 1/100 = 0.01 (wrong for a report agent).
    collector = dpi_ls.monitor(agent, agent_id="chandra-finops", human_baseline=1)   # line 2

    result = await Runner.run(
        agent,
        "Analyze my AWS account billing over the last 3 days. "
        "What regions are costing me the most money?",
    )

    print("\n--- Agent Final Output ---")
    # Strip any non-ASCII characters (emoji etc.) so the output prints
    # cleanly on Windows terminals that default to cp1252.
    safe_output = result.final_output.encode("ascii", errors="ignore").decode("ascii")
    print(safe_output)

    # -----------------------------------------------------------------
    # Run the LangGraph Q evaluator NOW - inside the live event loop -
    # so it can schedule async futures. If we leave it to the atexit
    # finalizer the interpreter has already started tearing down and
    # asyncio refuses to accept new coroutines.
    # -----------------------------------------------------------------
    outputs = collector.outputs_for_q()
    if outputs and collector.quality is None:
        try:
            q = await asyncio.get_running_loop().run_in_executor(
                None, dpi_ls.evaluate_quality, outputs
            )
            collector.set_quality(q.accuracy, q.consistency, q.hallucination_rate)
            print(
                f"\ndpi_ls Q score: accuracy={q.accuracy:.3f}  "
                f"consistency={q.consistency:.3f}  "
                f"hallucination={q.hallucination_rate:.3f}  "
                f"(source: {q.source})"
            )
        except Exception as exc:
            print(f"\ndpi_ls Q evaluator skipped: {exc}")


if __name__ == "__main__":
    # asyncio.run(main())

    asyncio.run(run_agent_observation())