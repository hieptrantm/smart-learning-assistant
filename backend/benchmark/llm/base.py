from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import BaseMessage


class BaseLLM(ABC):
    def __init__(self, model_name: str, **kwargs) -> None:
        self.model_name = model_name
        self.kwargs = kwargs

    @abstractmethod
    async def _agenerate(self, messages: list[BaseMessage], **kwargs) -> Any:
        pass

    @abstractmethod
    def invoke(self, messages: list[BaseMessage], **kwargs) -> Any:
        pass

    @abstractmethod
    async def ainvoke(self, messages: list[BaseMessage], **kwargs) -> Any:
        pass

    @abstractmethod
    def stream(self, messages: list[BaseMessage], **kwargs) -> Any:
        pass

    @abstractmethod
    async def astream(self, messages: list[BaseMessage], **kwargs) -> Any:
        pass

    @property
    def _llm_type(self) -> str:
        return "benchmark_base_llm"

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            **self.kwargs,
        }
