"""
check_arize_langchain.py
------------------------
Single-turn LangChain LCEL chain on AWS Bedrock, instrumented with Arize.

Run:
    uv run tests/check_arize_langchain.py

Traces appear in Arize under project: langchain-arize-test
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ── 1. Load & validate creds ──────────────────────────────────────────────────
load_dotenv(override=True)

ARIZE_SPACE_ID        = os.getenv("ARIZE_SPACE_ID")
ARIZE_API_KEY         = os.getenv("ARIZE_API_KEY")
BEDROCK_MODEL_ID      = os.getenv("BEDROCK_MODEL_ID")
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

log.info("ARIZE_SPACE_ID        = %s", ARIZE_SPACE_ID or "NOT SET ❌")
log.info("ARIZE_API_KEY         = %s", (ARIZE_API_KEY[:6] + "..." if ARIZE_API_KEY else "NOT SET ❌"))
log.info("BEDROCK_MODEL_ID      = %s", BEDROCK_MODEL_ID or "NOT SET ❌")
log.info("AWS_ACCESS_KEY_ID     = %s", (AWS_ACCESS_KEY_ID[:6] + "..." if AWS_ACCESS_KEY_ID else "NOT SET ❌"))
log.info("AWS_SECRET_ACCESS_KEY = %s", (AWS_SECRET_ACCESS_KEY[:6] + "..." if AWS_SECRET_ACCESS_KEY else "NOT SET ❌"))
log.info("AWS_DEFAULT_REGION    = %s", AWS_DEFAULT_REGION)

if not all([ARIZE_SPACE_ID, ARIZE_API_KEY, BEDROCK_MODEL_ID, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
    raise EnvironmentError("One or more required env vars are missing — check your .env file")

log.info("All creds loaded ✅")

# ── 2. Monkey-patch: strip stopSequences from ChatBedrockConverse body ────────
#
# langchain-aws's _converse_params always injects stopSequences into
# inferenceConfig. Qwen3 (and some other Bedrock models) reject this field
# entirely — even when the value is an empty list.
# We wrap _converse_params and pop the key out of inferenceConfig before
# returning, so it never reaches the Converse API call.
#
try:
    from langchain_aws.chat_models import bedrock_converse as _bc_mod
    from langchain_aws import ChatBedrockConverse as _CBC

    _orig_converse_params = _CBC._converse_params

    def _patched_converse_params(self, **kwargs):
        result = _orig_converse_params(self, **kwargs)
        # inferenceConfig is a dict; pop stopSequences if present
        if isinstance(result.get("inferenceConfig"), dict):
            result["inferenceConfig"].pop("stopSequences", None)
            # Also remove inferenceConfig entirely if now empty
            if not result["inferenceConfig"]:
                result.pop("inferenceConfig", None)
        log.debug("Monkey-patch: removed stopSequences from inferenceConfig")
        return result

    _CBC._converse_params = _patched_converse_params
    log.info("Monkey-patch applied: stopSequences suppressed for ChatBedrockConverse ✅")

except Exception as patch_err:
    log.warning(
        "Could not apply stopSequences monkey-patch (%s). "
        "If the chain fails with a stopSequences error, upgrade langchain-aws "
        "or switch to a model that supports it.",
        patch_err,
    )

# ── 3. Register Arize tracer + instrument LangChain ───────────────────────────
from arize.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

log.info("Registering Arize tracer provider...")
tracer_provider = register(
    space_id=ARIZE_SPACE_ID,
    api_key=ARIZE_API_KEY,
    project_name="langchain-arize-test",
)
log.info("Tracer provider registered ✅")

log.info("Instrumenting LangChain...")
LangChainInstrumentor().instrument(tracer_provider=tracer_provider, skip_dep_check=True)
log.info("Instrumentation complete ✅")

# ── 4. Build the LCEL chain (Bedrock via langchain-aws) ───────────────────────
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

log.info("Building LangChain LCEL chain with model: %s", BEDROCK_MODEL_ID)

llm = ChatBedrockConverse(
    model_id=BEDROCK_MODEL_ID,
    region_name=AWS_DEFAULT_REGION,
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a concise assistant. Answer in under 150 words."),
        ("human", "{question}"),
    ]
)

chain = prompt | llm | StrOutputParser()
log.info("Chain built ✅")

# ── 5. Run ────────────────────────────────────────────────────────────────────
async def main() -> None:
    question = "List 3 key facts about the Moon in bullet points."
    log.info("Invoking chain with question: %s", question)

    result: str = await chain.ainvoke({"question": question})

    log.info("Chain finished ✅ — traces should appear in Arize within ~30s")
    log.info("Check: https://app.arize.com → Tracing → project: langchain-arize-test")

    print("\n--- LangChain Final Output ---")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())