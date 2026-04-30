from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Iterator, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from langchain_together import ChatTogether

from benchmark.config import (
    BENCHMARK_LLM_MODEL,
    BENCHMARK_LLM_TEMPERATURE,
    BENCHMARK_MAX_TOKENS,
    BENCHMARK_TOGETHER_API_KEY,
)
from benchmark.llm.base import BaseLLM


logger = logging.getLogger(__name__)


class TogetherLLM(BaseLLM):
    def __init__(
        self,
        together_api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        together_api_key = together_api_key or BENCHMARK_TOGETHER_API_KEY
        model_name = model_name or BENCHMARK_LLM_MODEL
        if not together_api_key or not model_name:
            raise ValueError("Benchmark Together LLM requires API key and model name")

        params = {
            "temperature": BENCHMARK_LLM_TEMPERATURE,
            "max_tokens": BENCHMARK_MAX_TOKENS,
            **kwargs,
        }
        super().__init__(model_name=model_name, together_api_key=together_api_key, **params)
        self.client = ChatTogether(
            together_api_key=together_api_key,
            model=model_name,
            **params,
        )
        logger.info("Initialized benchmark TogetherLLM with model: %s", model_name)

    async def _agenerate(self, messages: list[BaseMessage], **kwargs) -> LLMResult:
        return await self.client.agenerate([messages], **kwargs)

    def _generate(self, messages: list[BaseMessage], **kwargs) -> LLMResult:
        return self.client.generate([messages], **kwargs)

    def invoke(self, messages: list[BaseMessage], **kwargs) -> Any:
        return self._generate(messages, **kwargs)

    async def ainvoke(self, messages: list[BaseMessage], **kwargs) -> Any:
        return await self.client.ainvoke(messages, **kwargs)

    def stream(self, messages: list[BaseMessage], **kwargs) -> Iterator[Any]:
        for chunk in self.client.stream(messages, **kwargs):
            yield chunk.content if hasattr(chunk, "content") else str(chunk)

    async def astream(self, messages: list[BaseMessage], **kwargs) -> AsyncIterator[Any]:
        async for chunk in self.client.astream(messages, **kwargs):
            yield chunk.content if hasattr(chunk, "content") else str(chunk)

    async def astream_log(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> AsyncIterator[Any]:
        async for chunk in self.astream(input, **kwargs):
            yield chunk

    def predict(self, text: str, **kwargs) -> str:
        result = self._generate([HumanMessage(content=text)], **kwargs)
        return result.generations[0][0].text

    async def apredict(self, text: str, **kwargs) -> str:
        result = await self._agenerate([HumanMessage(content=text)], **kwargs)
        return result.generations[0][0].text

    def predict_messages(self, messages: list[BaseMessage], **kwargs) -> BaseMessage:
        result = self._generate(messages, **kwargs)
        return AIMessage(content=result.generations[0][0].text)

    async def apredict_messages(self, messages: list[BaseMessage], **kwargs) -> BaseMessage:
        result = await self._agenerate(messages, **kwargs)
        return AIMessage(content=result.generations[0][0].text)

    @property
    def _llm_type(self) -> str:
        return "benchmark_together_llm"
