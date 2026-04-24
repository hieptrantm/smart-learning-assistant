#!/usr/bin/env python3
"""
Base LLM class for LangGraph Agent
Defines the interface for LLM implementations compatible with LangChain
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict, Union
from langchain_core.messages import BaseMessage


class BaseLLM(ABC):
    """Base class for LLM implementations compatible with LangChain"""
    
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs
    
    @abstractmethod
    async def _agenerate(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Async generation - required by LangChain"""
        pass
    
    @abstractmethod
    def invoke(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Async generation - required by LangChain"""
        pass
    
    @abstractmethod
    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Async generation - required by LangChain"""
        pass
    
    @abstractmethod
    def stream(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Async generation - required by LangChain"""
        pass
    
    @abstractmethod
    async def astream(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Async generation - required by LangChain"""
        pass
    
    def _generate(self, messages: List[BaseMessage], **kwargs) -> Any:
        """Sync generation - required by LangChain"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._agenerate(messages, **kwargs))
                    return future.result()
            else:
                return asyncio.run(self._agenerate(messages, **kwargs))
        except Exception as e:
            raise e
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM - required by LangChain"""
        return "base_llm"
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model"""
        return {
            "model_name": self.model_name,
            "openai_api_base": self.openai_api_base,
            **self.kwargs
        } 