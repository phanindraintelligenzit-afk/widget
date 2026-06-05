"""Raw boto3 Bedrock agent — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/raw_bedrock.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="raw-bedrock"`` once the script exits.

What this exercises
-------------------

* The detector in ``dpi_ls/frameworks/__init__.py`` does not match
  boto3 clients against any specific framework, so the dispatcher
  falls back to ``UnknownPatcher`` (the "graceful fallback" path the
  spec calls out). ``UnknownPatcher`` wraps the agent's ``invoke``
  method so the collector still observes one
  ``agent_runs_completed`` (drives **P**) and captures the final
  text (drives V, G, and the Q evaluator's input).
* Token usage is captured manually inside ``BedrockAgent.invoke``
  via the same ``dpi_ls._state.get_collector()`` pattern the
  LangGraph and AutoGen examples use — so the **C** dimension is
  real.
"""
from __future__ import annotations

import os
from typing import Any

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

import dpi_ls
from dpi_ls import _state


class BedrockAgent:
    """A minimal ``invoke(prompt) -> str`` wrapper around boto3 bedrock-runtime.

    The class name and method are intentionally chosen so the
    ``UnknownPatcher`` recognises ``invoke`` and wraps it.
    """

    name = "raw-bedrock-agent"
    description = "A direct boto3 Bedrock agent — no framework in the loop."

    def __init__(self, model_id: str, region_name: str = "us-east-1") -> None:
        self.model_id = model_id
        self.region_name = region_name
        self._client = boto3.client("bedrock-runtime", region_name=region_name)

    def invoke(self, prompt: str) -> str:
        response = self._client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[
                {
                    "text": (
                        "You are a concise analyst. Answer in under 200 words. "
                        "Format as Markdown with at least one '##' section header. "
                        "Do not include any email addresses, phone numbers, or API keys."
                    ),
                }
            ],
            inferenceConfig={"maxTokens": 800},
        )

        # ---- pull the answer text + token usage ----
        output = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(part.get("text", "") for part in output if "text" in part)
        usage = response.get("usage", {})
        in_t = int(usage.get("inputTokens", 0))
        out_t = int(usage.get("outputTokens", 0))
        cost = (in_t + out_t) * 0.000001  # $0.001/1k tokens blended

        # ---- push signals into the active collector ----
        # UnknownPatcher does not inspect framework-specific response
        # shapes, so we record tokens manually here. This is the
        # same hook the LangGraph and AutoGen examples use.
        collector = _state.get_collector()
        if collector is not None and text:
            collector.record_llm_call(
                text,
                tokens_in=in_t,
                tokens_out=out_t,
                cost=cost,
                ok=True,
            )
        return text


def main() -> None:
    agent = BedrockAgent(
        model_id=os.environ["BEDROCK_MODEL_ID"],
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    dpi_ls.monitor(
        agent,
        agent_id="raw-bedrock",
        agent_name="Raw boto3 Bedrock Agent",
        human_baseline=1,
    )

    prompt = (
        "Give three concrete reasons a FinOps team should adopt a "
        "unified AI-agent scoring framework across all of their AI "
        "agents. Use Markdown section headers."
    )
    result = agent.invoke(prompt)
    print("\n--- Raw Bedrock Final Output ---")
    print(result.encode("ascii", errors="ignore").decode("ascii"))


if __name__ == "__main__":
    os.environ.setdefault("DPI_LS_NO_BLOCK", "1")
    main()
