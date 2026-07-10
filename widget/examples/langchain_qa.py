"""LangChain single-turn Q&A chain — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/langchain_qa.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="langchain-qa"`` once the script exits.

What this exercises
-------------------

* ``LangChainPatcher`` (from ``dpi_ls/frameworks/langchain.py``) wraps
  ``chain.ainvoke`` so the collector observes one ``agent_runs_completed``.
  The chain here stops at the LLM (no ``StrOutputParser``) so the result
  is an ``AIMessage`` — that lets the patcher pull ``usage_metadata``
  and record real token counts (drives **C**) without any manual
  ``record_llm_call`` plumbing.
* The output is a short Markdown list with ``##`` headers so V / G / R
  scanners all see the run as structured, governance-clean, and
  incident-free.
* The LangGraph Q evaluator inside ``dpi_ls`` scores the output
  for the **Q** dimension.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

load_dotenv(override=True)

import dpi_ls


def _build_llm() -> ChatBedrockConverse:
    model_id = os.environ["BEDROCK_MODEL_ID"]
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    kwargs: dict[str, Any] = {"model_id": model_id}
    if region:
        kwargs["region_name"] = region
    return ChatBedrockConverse(**kwargs)


PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a concise support agent. Answer the user's question "
            "in under 200 words. Format the response as Markdown with at "
            "least one '##' section header. Do not include any email "
            "addresses, phone numbers, or API keys.",
        ),
        ("human", "{question}"),
    ]
)


def _build_chain():
    llm = _build_llm()
    # No StrOutputParser — leaving the result as an AIMessage means the
    # LangChainPatcher can read usage_metadata off it and record real
    # token counts (drives the C dimension). The script below extracts
    # ``.content`` for printing.
    return PROMPT | llm


async def main() -> None:
    chain = _build_chain()
    dpi_ls.monitor(
        chain,
        agent_id="langchain-qa",
        agent_name="LangChain Q&A Agent",
        human_baseline=1,
    )

    question = (
        "A user is asking how to safely roll out an AI agent into a "
        "production customer support workflow. Give three concrete "
        "recommendations."
    )
    result = await chain.ainvoke({"question": question})

    # ``result`` is an AIMessage — pull the text content out for display.
    text = getattr(result, "content", str(result))
    print("\n--- LangChain Final Output ---")
    print(text.encode("ascii", errors="ignore").decode("ascii"))


if __name__ == "__main__":
    os.environ.setdefault("DPI_LS_NO_BLOCK", "1")
    asyncio.run(main())
