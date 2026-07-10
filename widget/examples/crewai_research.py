"""CrewAI 2-agent research crew — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/crewai_research.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="crewai-research"`` once the script exits.

What this exercises
-------------------

* ``CrewAIPatcher`` (from ``dpi_ls/frameworks/crewai.py``) wraps
  ``crew.kickoff`` (now using ``object.__setattr__`` to bypass
  Pydantic v2's frozen-model guard). The collector records one
  ``agent_runs_completed`` per kickoff, plus one ``attempts`` and
  one ``successful`` per task the crew executes (drives **P** and
  **E**).
* Each task output is captured into the collector's output buffer,
  so the LangGraph Q evaluator inside ``dpi_ls`` scores the union of
  the crew's prose for the **Q** dimension.
* The model configured in ``BEDROCK_MODEL_ID`` (qwen on this
  account) rejects the ``stopSequences`` field that CrewAI's
  executor always sends. The ``BedrockCompletionNoStop`` shim below
  overrides the ``stop`` setter to a no-op so the rest of CrewAI's
  wiring works unchanged. Models that do support ``stopSequences``
  (Claude, Llama) work without the shim.
* Token usage is captured manually by wrapping the boto3
  ``bedrock-runtime.converse`` call. ``CrewAIPatcher`` only sees the
  final ``CrewOutput`` (a string), so the **C** dimension needs this
  small bridge to be non-zero.
"""
from __future__ import annotations

import os
from typing import Any, Sequence

from dotenv import load_dotenv

load_dotenv(override=True)

from crewai import Agent, Crew, Process, Task
from crewai.llms.providers.bedrock.completion import BedrockCompletion

import boto3

import dpi_ls
from dpi_ls import _state


class BedrockCompletionNoStop(BedrockCompletion):
    """CrewAI's executor always populates ``self.llm.stop = [...]``.

    Some Bedrock models (e.g. hosted Qwen) reject the
    ``stopSequences`` field that CrewAI then forwards. Overriding
    the ``stop`` setter to a no-op keeps the rest of the wiring
    intact and lets the request go through.

    Drop the shim and use ``BedrockCompletion`` directly for models
    that support stop sequences (Claude, Llama).
    """

    @BedrockCompletion.stop.setter  # type: ignore[attr-defined]
    def stop(self, value: Sequence[str] | str | None) -> None:  # noqa: D401
        return None

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        # Wrap the underlying boto3 ``converse`` so we can capture
        # usage data after every call. CrewAI's public ``call`` API
        # only returns the assistant text — usage is dropped otherwise.
        original_converse = self.client.converse

        def _converse_with_metrics(*c_args: Any, **c_kwargs: Any):
            response = original_converse(*c_args, **c_kwargs)
            try:
                usage = response.get("usage", {}) if isinstance(response, dict) else {}
                in_t = int(usage.get("inputTokens", 0))
                out_t = int(usage.get("outputTokens", 0))
                output = response.get("output", {}).get("message", {}).get("content", [])
                text = "".join(p.get("text", "") for p in output if "text" in p)
                cost = (in_t + out_t) * 0.000001
                collector = _state.get_collector()
                if collector is not None and text:
                    collector.record_llm_call(
                        text,
                        tokens_in=in_t,
                        tokens_out=out_t,
                        cost=cost,
                        ok=True,
                    )
            except Exception:  # pragma: no cover - metrics are best-effort
                pass
            return response

        # Bind the wrapper onto the instance so each agent's LLM has
        # its own closure over the original converse.
        self.client.converse = _converse_with_metrics  # type: ignore[method-assign]


def _build_llm(model_id: str) -> BedrockCompletion:
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return BedrockCompletionNoStop(model=model_id, region_name=region)


def _build_crew() -> Crew:
    # Each agent gets its own LLM instance — the per-instance
    # converse wrapper captures tokens for that agent's calls.
    llm_researcher = _build_llm(os.environ["BEDROCK_MODEL_ID"])
    llm_writer = _build_llm(os.environ["BEDROCK_MODEL_ID"])

    researcher = Agent(
        role="Cloud Cost Researcher",
        goal="Identify the three highest-impact FinOps optimization levers",
        backstory=(
            "You are a senior cloud economist who specialises in AWS cost "
            "reduction. Your analysis is grounded in public AWS pricing "
            "patterns and well-known FinOps best practices."
        ),
        llm=llm_researcher,
        allow_delegation=False,
        verbose=False,
    )
    writer = Agent(
        role="Executive Brief Writer",
        goal="Turn the researcher's findings into a concise Markdown brief",
        backstory=(
            "You are a concise executive writer. You produce tight, "
            "structured Markdown briefs with '##' section headers."
        ),
        llm=llm_writer,
        allow_delegation=False,
        verbose=False,
    )

    research_task = Task(
        description=(
            "Identify the three highest-impact FinOps optimization levers "
            "for an enterprise AWS account. For each lever, list the "
            "mechanism, the typical savings range, and one concrete risk."
        ),
        expected_output="A bulleted list of three levers with mechanism, savings, and risk.",
        agent=researcher,
    )
    write_task = Task(
        description=(
            "Take the researcher's bullets and turn them into a polished "
            "Markdown brief with '##' section headers. Keep it under 350 "
            "words. No PII, no API keys, no phone numbers."
        ),
        expected_output="A short Markdown brief.",
        agent=writer,
    )

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
        verbose=False,
    )


def main() -> None:
    crew = _build_crew()
    dpi_ls.monitor(
        crew,
        agent_id="crewai-research",
        agent_name="CrewAI Research Crew",
        human_baseline=1,
    )

    result = crew.kickoff()
    text = getattr(result, "raw", "") or str(result)
    print("\n--- CrewAI Final Output ---")
    print(text.encode("ascii", errors="ignore").decode("ascii"))


if __name__ == "__main__":
    os.environ.setdefault("DPI_LS_NO_BLOCK", "1")
    main()
