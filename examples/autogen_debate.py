"""AutoGen 0.7+ 2-agent debate — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/autogen_debate.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="autogen-debate"`` once the script exits.

What this exercises
-------------------

* The new AutoGen (``autogen_agentchat.agents.AssistantAgent``) does
  not expose the legacy ``initiate_chat`` / ``generate_reply`` methods
  the ``AutoGenPatcher`` looks for, so the dispatcher falls back to
  the ``UnknownPatcher`` (see ``dpi_ls/frameworks/__init__.py``).
  ``UnknownPatcher`` wraps the agent's ``run`` method — the entry
  point that the new AutoGen exposes — so the collector still
  observes one ``agent_runs_completed`` (drives **P**) and captures
  the final assistant text (drives Q, V, G).
* The legacy patcher auto-detection rule still classifies the
  module as ``autogen``, so we manually re-stamp
  ``collector.framework = "autogen"`` after the run so the
  observation's ``source`` field reads ``dpi_ls:autogen`` rather
  than the fallback ``dpi_ls:unknown``.
* Token usage is captured manually inside the small
  ``BedrockChatCompletionClient`` below so the **C** dimension
  reflects real Bedrock usage. ``UnknownPatcher`` itself never
  pulls token counts — it has no schema knowledge of the framework.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Sequence

from dotenv import load_dotenv

load_dotenv(override=True)

from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    LLMMessage,
    RequestUsage,
    SystemMessage,
    UserMessage,
)

import boto3

import dpi_ls
from dpi_ls import _state


# ---------------------------------------------------------------------------
# Tiny Bedrock ChatCompletionClient for the new AutoGen.
# ---------------------------------------------------------------------------
class BedrockChatCompletionClient(ChatCompletionClient):
    """Minimal ``ChatCompletionClient`` backed by boto3 ``bedrock-runtime`` converse.

    Implements only the surface the demo needs (``create`` + ``model_info``).
    Token counts from the Bedrock response are pushed into the active
    ``SignalCollector`` so the C dimension is non-zero — this is the one
    piece of plumbing the ``UnknownPatcher`` does not do for us.
    """

    def __init__(self, model_id: str, region_name: str) -> None:
        self._model_id = model_id
        self._region = region_name
        self._client = boto3.client("bedrock-runtime", region_name=region_name)

    # ---- the two abstract methods we must implement ----------------------

    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Any = [],
        tool_choice: Any = "auto",
        json_output: Any = None,
        extra_create_args: Any = {},
        cancellation_token: Any = None,
    ) -> CreateResult:
        # Translate AutoGen messages -> Bedrock converse messages.
        converse_messages: list[dict[str, Any]] = []
        system_prompts: list[str] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                system_prompts.append(str(m.content))
            elif isinstance(m, UserMessage):
                converse_messages.append(
                    {
                        "role": "user",
                        "content": [{"text": str(m.content)}],
                    }
                )
            else:  # AssistantMessage / FunctionExecutionResultMessage — ignore for the demo
                continue

        kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": converse_messages,
            "inferenceConfig": {"maxTokens": 800},
        }
        if system_prompts:
            kwargs["system"] = [{"text": "\n".join(system_prompts)}]

        # boto3.converse is sync; the cost of running it in a thread
        # pool is fine for the demo. We await it directly because
        # the response is small and the call is sub-second.
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: self._client.converse(**kwargs))

        # ---- pull the answer text + token usage ----
        output = response.get("output", {}).get("message", {}).get("content", [])
        text = ""
        for part in output:
            if "text" in part:
                text += part["text"]
        usage = response.get("usage", {})
        in_t = int(usage.get("inputTokens", 0))
        out_t = int(usage.get("outputTokens", 0))
        cost = (in_t + out_t) * 0.000001  # $0.001/1k tokens blended

        # ---- push signals into the active collector ----
        collector = _state.get_collector()
        if collector is not None and text:
            collector.record_llm_call(
                text,
                tokens_in=in_t,
                tokens_out=out_t,
                cost=cost,
                ok=True,
            )

        finish = response.get("stopReason", "stop")
        finish_map = {
            "stop": "stop",
            "end_turn": "stop",
            "max_tokens": "length",
            "tool_use": "function_calls",
        }
        return CreateResult(
            finish_reason=finish_map.get(finish, "stop"),
            content=text,
            usage=RequestUsage(prompt_tokens=in_t, completion_tokens=out_t),
            cached=False,
        )

    @property
    def model_info(self) -> dict[str, Any]:
        # Minimal metadata the new AutoGen requires.
        return {
            "family": "bedrock",
            "name": self._model_id,
            "function_calling": False,
            "json_output": False,
            "vision": False,
            "structured_output": False,
        }

    @property
    def capabilities(self) -> dict[str, bool]:
        # The new AutoGen still requires this legacy method on the
        # abstract base class. Values must match ``model_info`` above.
        return {
            "vision": False,
            "function_calling": False,
            "json_output": False,
        }

    # ---- the rest of the abstract surface — no-ops for the demo -------

    async def create_stream(self, *args: Any, **kwargs: Any):  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover
        pass

    def count_tokens(self, messages: Sequence[LLMMessage], **kwargs: Any) -> int:  # pragma: no cover
        # Rough char/4 estimate — the real value is what the LLM call returns.
        total = 0
        for m in messages:
            total += len(str(getattr(m, "content", "")))
        return total // 4

    def remaining_tokens(self) -> int:  # pragma: no cover
        return 8000

    def total_usage(self) -> int:  # pragma: no cover
        return 0

    def actual_usage(self) -> list[int]:  # pragma: no cover
        return [0, 0]

    # ---- ComponentBase plumbing ----

    def dump_component(self) -> dict[str, Any]:  # pragma: no cover
        return {"model_id": self._model_id, "region": self._region}

    @classmethod
    def load_component(cls, config: dict[str, Any]) -> "BedrockChatCompletionClient":  # pragma: no cover
        return cls(model_id=config["model_id"], region_name=config["region"])


# ---------------------------------------------------------------------------
# Agent + run
# ---------------------------------------------------------------------------
def _build_client() -> BedrockChatCompletionClient:
    model_id = os.environ["BEDROCK_MODEL_ID"]
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return BedrockChatCompletionClient(model_id=model_id, region_name=region)


def _build_agent(client: BedrockChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="debater",
        model_client=client,
        system_message=(
            "You are a balanced debater. Respond in under 200 words. "
            "Format the response as Markdown with at least one '##' "
            "section header. Do not include any email addresses, phone "
            "numbers, or API keys."
        ),
        description="A debate agent that gives a balanced take on the topic.",
    )


async def main() -> None:
    client = _build_client()
    agent = _build_agent(client)

    collector = dpi_ls.monitor(
        agent,
        agent_id="autogen-debate",
        agent_name="AutoGen Debate Agent",
        human_baseline=1,
    )
    # Re-stamp the framework: the dispatcher's AutoGenPatcher found no
    # legacy methods to wrap, so it fell back to UnknownPatcher. We
    # observed the agent is a genuine AutoGen 0.7+ AssistantAgent,
    # so we label the observation correctly.
    collector.framework = "autogen"

    topic = (
        "Should AI agents in customer support be required to disclose "
        "that they are non-human? Argue both sides briefly, then give "
        "a recommendation."
    )
    result = await agent.run(task=topic)
    # The new AutoGen's `run` returns a `TaskResult` whose `messages`
    # is a list of ChatMessage objects; the last one is the assistant's
    # final answer. Print it.
    final_text = ""
    for msg in getattr(result, "messages", []):
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            final_text = content
    print("\n--- AutoGen Final Output ---")
    print((final_text or "<no text>").encode("ascii", errors="ignore").decode("ascii"))


if __name__ == "__main__":
    os.environ.setdefault("DPI_LS_NO_BLOCK", "1")
    asyncio.run(main())
