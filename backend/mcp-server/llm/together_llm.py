#!/usr/bin/env python3
import logging
import os
import sys
from typing import Any, List, Optional, Dict, Iterator, AsyncIterator
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import Generation, LLMResult
from langchain_core.runnables import RunnableConfig
from langchain_together import ChatTogether

from .base import BaseLLM

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TogetherLLM(BaseLLM):
    """Together AI LLM implementation using ChatTogether from LangChain"""
    
    def __init__(
        self, 
        together_api_key: Optional[str] = None,
        model_name: str = None,
        **kwargs
    ):
        """
        Initialize Together AI LLM
        
        Args:
            together_api_key: Together AI API key (if None, reads from TOGETHER_API_KEY env)
            model_name: Model name to use (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        """
        # Get from environment if not provided
        together_api_key = together_api_key or os.getenv('TOGETHER_API_KEY')
        model_name = model_name or os.getenv('TOGETHER_MODEL_NAME', 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
        
        if not together_api_key or not model_name:
            raise ValueError("together_api_key and model_name must be provided")
        
        # Initialize base class
        super().__init__(
            model_name=model_name,
            together_api_key=together_api_key,
            **kwargs
        )
        
        try:
            # Initialize ChatTogether client
            self.client = ChatTogether(
                together_api_key=together_api_key,
                model=model_name,
                **kwargs
            )
            logger.info(f"Initialized TogetherLLM with model: {model_name}")
        except Exception as e:
            logger.error(f"Error initializing ChatTogether client: {e}")
            raise e
    
    async def _agenerate(self, messages: List[BaseMessage], **kwargs) -> LLMResult:
        """Async generation - required by LangChain"""
        try:
            # ChatTogether directly accepts LangChain messages
            response = await self.client.agenerate([messages], **kwargs)
            return response
            
        except Exception as e:
            logger.error(f"Error in _agenerate: {e}")
            raise e
    
    def _generate(self, messages: List[BaseMessage], **kwargs) -> LLMResult:
        """Sync generation - required by BaseLLM"""
        try:
            # ChatTogether directly accepts LangChain messages
            response = self.client.generate([messages], **kwargs)
            return response
            
        except Exception as e:
            logger.error(f"Error in _generate: {e}")
            raise e
    
    # Streaming methods
    async def astream(self, messages: Any, **kwargs) -> AsyncIterator[Any]:
        """Async streaming - required by LangChain"""
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            messages = messages
        else:
            raise ValueError("messages must be a list of BaseMessage")
        
        try:
            # Stream using ChatTogether
            async for chunk in self.client.astream(messages, **kwargs):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)
                    
        except Exception as e:
            logger.error(f"Error in astream: {e}")
            raise e
    
    def stream(self, messages: Any, **kwargs) -> Iterator[Any]:
        """Sync streaming - required by LangChain"""
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            messages = messages
        else:
            raise ValueError("messages must be a list of BaseMessage")
        
        try:
            # Stream using ChatTogether
            for chunk in self.client.stream(messages, **kwargs):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)
                    
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            raise e
    
    async def astream_log(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> AsyncIterator[Any]:
        """Async streaming with logging - for compatibility"""
        async for chunk in self.astream(input, **kwargs):
            yield chunk
    
    def stream_log(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Iterator[Any]:
        """Sync streaming with logging - for compatibility"""
        for chunk in self.stream(input, **kwargs):
            yield chunk
    
    # Implement required abstract methods
    def invoke(self, messages: Any, **kwargs) -> Any:
        """Invoke the LLM synchronously"""
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            return self._generate(messages, **kwargs)
        else:
            raise ValueError("Input must be a list of BaseMessage")
    
    async def ainvoke(self, messages: Any, **kwargs) -> Any:
        """Invoke the LLM asynchronously, returns AIMessage for agent"""
        if isinstance(messages, list) and all(isinstance(msg, BaseMessage) for msg in messages):
            # Use ChatTogether's ainvoke which returns AIMessage directly
            response = await self.client.ainvoke(messages, **kwargs)
            return response
        else:
            raise ValueError("messages must be a list of BaseMessage")
    
    def predict(self, text: str, **kwargs) -> str:
        """Predict text - simplified for compatibility"""
        messages: List[BaseMessage] = [HumanMessage(content=text)]
        result = self._generate(messages, **kwargs)
        return result.generations[0][0].text
    
    async def apredict(self, text: str, **kwargs) -> str:
        """Async predict text - simplified for compatibility"""
        messages: List[BaseMessage] = [HumanMessage(content=text)]
        result = await self._agenerate(messages, **kwargs)
        return result.generations[0][0].text
    
    def predict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        """Predict messages - simplified for compatibility"""
        result = self._generate(messages, **kwargs)
        return AIMessage(content=result.generations[0][0].text)
    
    async def apredict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        """Async predict messages - simplified for compatibility"""
        result = await self._agenerate(messages, **kwargs)
        return AIMessage(content=result.generations[0][0].text)
    
    def generate_prompt(self, prompts: List[Any], **kwargs) -> LLMResult:
        """Generate from prompts - simplified for compatibility"""
        messages = []
        for prompt in prompts:
            if hasattr(prompt, 'to_messages'):
                messages.extend(prompt.to_messages())
            elif isinstance(prompt, list):
                messages.extend(prompt)
        return self._generate(messages, **kwargs)
    
    async def agenerate_prompt(self, prompts: List[Any], **kwargs) -> LLMResult:
        """Async generate from prompts - simplified for compatibility"""
        messages = []
        for prompt in prompts:
            if hasattr(prompt, 'to_messages'):
                messages.extend(prompt.to_messages())
            elif isinstance(prompt, list):
                messages.extend(prompt)
        return await self._agenerate(messages, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM - required by LangChain"""
        return "together_llm"
