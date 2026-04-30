from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from benchmark.config import (
    BENCHMARK_FALLBACK_LLM_MODEL,
    BENCHMARK_LLM_MAX_RETRIES,
    BENCHMARK_LLM_RETRY_BASE_SECONDS,
)
from benchmark.llm.together_llm import TogetherLLM


logger = logging.getLogger(__name__)


class BenchmarkLLMService:
    """Subset of the data-ingestor LLM service API, backed by benchmark TogetherLLM."""

    def __init__(self, client: TogetherLLM | None = None) -> None:
        self.client = client or TogetherLLM()
        self._fallback_client: TogetherLLM | None = None

    def identify_merge_candidates(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from rag_config import CONCEPT_MERGE_SYSTEM_PROMPT, CONCEPT_MERGE_USER_PROMPT

        prompt = CONCEPT_MERGE_USER_PROMPT.format(entities=json.dumps(entities, ensure_ascii=False))
        response = self._call_llm(CONCEPT_MERGE_SYSTEM_PROMPT, prompt)
        return self._parse_json_array(response)

    async def _acall_llm(self, system_prompt: str, user_prompt: str) -> str:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await self._ainvoke_with_resilience(messages)
        return response.content

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self._invoke_with_resilience(messages)
        if hasattr(response, "generations"):
            return response.generations[0][0].text
        return response.content

    async def _ainvoke_with_resilience(self, messages: list[Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, BENCHMARK_LLM_MAX_RETRIES + 1):
            try:
                return await self.client.ainvoke(messages)
            except (InternalServerError, APIConnectionError, APITimeoutError, RateLimitError) as exc:
                last_exc = exc
                if not self._should_retry(exc, attempt):
                    break
                delay = BENCHMARK_LLM_RETRY_BASE_SECONDS * attempt
                logger.warning(
                    "Primary benchmark model %s failed on attempt %s/%s: %s. Retrying in %.1fs.",
                    self.client.model_name,
                    attempt,
                    BENCHMARK_LLM_MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        fallback = self._get_fallback_client()
        if fallback is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Benchmark LLM request failed without a captured exception")

        logger.warning(
            "Falling back from benchmark model %s to %s after repeated transient failures.",
            self.client.model_name,
            fallback.model_name,
        )
        return await fallback.ainvoke(messages)

    def _invoke_with_resilience(self, messages: list[Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, BENCHMARK_LLM_MAX_RETRIES + 1):
            try:
                return self.client.invoke(messages)
            except (InternalServerError, APIConnectionError, APITimeoutError, RateLimitError) as exc:
                last_exc = exc
                if not self._should_retry(exc, attempt):
                    break
                delay = BENCHMARK_LLM_RETRY_BASE_SECONDS * attempt
                logger.warning(
                    "Primary benchmark model %s failed on attempt %s/%s: %s. Retrying in %.1fs.",
                    self.client.model_name,
                    attempt,
                    BENCHMARK_LLM_MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

        fallback = self._get_fallback_client()
        if fallback is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Benchmark LLM request failed without a captured exception")

        logger.warning(
            "Falling back from benchmark model %s to %s after repeated transient failures.",
            self.client.model_name,
            fallback.model_name,
        )
        return fallback.invoke(messages)

    @staticmethod
    def _should_retry(exc: Exception, attempt: int) -> bool:
        if attempt >= BENCHMARK_LLM_MAX_RETRIES:
            return False
        if isinstance(exc, InternalServerError):
            status_code = getattr(exc, "status_code", None)
            return status_code in {500, 502, 503, 504} or status_code is None
        return True

    def _get_fallback_client(self) -> TogetherLLM | None:
        fallback_model = (BENCHMARK_FALLBACK_LLM_MODEL or "").strip()
        if not fallback_model or fallback_model == self.client.model_name:
            return None
        if self._fallback_client is None:
            self._fallback_client = TogetherLLM(model_name=fallback_model)
        return self._fallback_client

    async def aextract_entities_from_chunk(self, content: str) -> list[dict[str, Any]]:
        from rag_config import ENTITY_EXTRACTION_SYSTEM_PROMPT, ENTITY_EXTRACTION_USER_PROMPT

        response = await self._acall_llm(
            ENTITY_EXTRACTION_SYSTEM_PROMPT,
            ENTITY_EXTRACTION_USER_PROMPT.format(chunk_content=content),
        )
        return self._parse_json_array(response)

    async def aextract_relations_from_chunk(self, entities: list[dict[str, Any]], content: str) -> list[dict[str, Any]]:
        from rag_config import RELATION_EXTRACTION_SYSTEM_PROMPT, RELATION_EXTRACTION_USER_PROMPT

        response = await self._acall_llm(
            RELATION_EXTRACTION_SYSTEM_PROMPT,
            RELATION_EXTRACTION_USER_PROMPT.format(
                entities=json.dumps(entities, ensure_ascii=False),
                chunk_content=content,
            ),
        )
        return self._parse_json_array(response)

    @staticmethod
    def _parse_json_array(raw_text: str) -> list[dict[str, Any]]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        try:
            payload = json.loads(cleaned)
            return payload if isinstance(payload, list) else []
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON array from benchmark LLM output: %s", exc)
            return []
