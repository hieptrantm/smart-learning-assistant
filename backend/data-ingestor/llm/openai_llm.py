#!/usr/bin/env python3
"""
OpenAI LLM implementation for LangGraph Agent
Uses OpenAI API integration compatible with LangChain
"""

from json.tool import main
import logging
import os
import sys
from typing import Any, List, Optional, Dict, Iterator, AsyncIterator
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import Generation, LLMResult
from langchain_core.runnables import RunnableConfig
# from langchain_core.prompts import PromptValue  # Commented out due to import error
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from openai import OpenAI, AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .base import BaseLLM
load_dotenv()

class OpenAILLM(BaseLLM):
    """OpenAI LLM implementation using OpenAI API"""
    
    def __init__(self, openai_api_key: Optional[str] = None, openai_api_base: Optional[str] = None, model_name: str = None, **kwargs):
        if not openai_api_key or not model_name:
            raise ValueError("openai_api_key and model_name must be provided")
        
        super().__init__(model_name=model_name, openai_api_key=openai_api_key, openai_api_base=openai_api_base, **kwargs)
        client_kwargs = {"api_key": openai_api_key}
        if openai_api_base is not None:
            client_kwargs["base_url"] = openai_api_base
        try:
            # Sync client chỉ dùng cho invoke() / stream()
            self.client = OpenAI(**client_kwargs)
            # Async client dùng cho ainvoke() / astream() — không block event loop
            self.async_client = AsyncOpenAI(**client_kwargs)
        except Exception as e:
            logging.error(f"Error initializing OpenAI client: {e}")
            raise e
    
    async def _agenerate(self, messages: List[BaseMessage], **kwargs) -> LLMResult:
        """Async generation — dùng AsyncOpenAI để không block event loop"""
        try:
            openai_messages = self._convert_messages(messages)
            
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                stream=False,
                **kwargs
            )
            content = response.choices[0].message.content or getattr(response.choices[0].message, "reasoning_content", None) or ""
            generation = Generation(
                text=content,
                generation_info={
                    "finish_reason": response.choices[0].finish_reason,
                    "usage": response.usage.model_dump() if response.usage else None
                }
            )
            
            return LLMResult(generations=[[generation]])
            
        except Exception as e:
            logging.error(f"Error in _agenerate: {e}")
            raise e
    
    def _convert_messages(self, messages: List[BaseMessage]):
        """Convert langchain messages to OpenAI format"""
        openai_messages = []
        for m in messages:
            if hasattr(m, 'type') and m.type == 'system':
                openai_messages.append({"role": "system", "content": m.content})
            elif hasattr(m, 'type') and m.type == 'human':
                openai_messages.append({"role": "user", "content": m.content})
            elif hasattr(m, 'type') and m.type == 'ai':
                openai_messages.append({"role": "assistant", "content": m.content})
            else:
                openai_messages.append({"role": "user", "content": str(m.content)})
        return openai_messages
    
    # Streaming methods
    async def astream(self, messages: Any, **kwargs) -> AsyncIterator[Any]:
        """Async streaming — dùng AsyncOpenAI để không block event loop"""
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            messages = messages
        else:
            raise ValueError("messages must be a list of BaseMessage")
        
        try:
            openai_messages = self._convert_messages(messages)
            
            stream = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                content = delta.content or getattr(delta, "reasoning_content", None) or ""
                if content:
                    yield content
                    
        except Exception as e:
            logging.error(f"Error in astream: {e}")
            raise e
    
    def stream(self, messages: Any, **kwargs) -> Iterator[Any]:
        """Sync streaming - required by LangChain"""
        import asyncio
        
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            messages = messages
        else:
            raise ValueError("messages must be a list of BaseMessage")
        
        try:
            openai_messages = self._convert_messages(messages)
            
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                chunk_res = chunk.dict()
                delta = chunk_res.get("choices", [{}])[0].get("delta", {})
                
                # Get content from delta, prefer content over reasoning_content
                content = delta.get("content") or delta.get("reasoning_content") or ""
                
                # Only yield if there's actual content
                if content:
                    yield content
                    
        except Exception as e:
            logging.error(f"Error in stream: {e}")
            raise e
    
    async def astream_log(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> AsyncIterator[Any]:
        """Async streaming with logging - for compatibility"""
        async for chunk in self.astream(input, config, **kwargs):
            yield chunk
    
    def stream_log(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Iterator[Any]:
        """Sync streaming with logging - for compatibility"""
        for chunk in self.stream(input, config, **kwargs):
            yield chunk
    
    # Implement required abstract methods
    def invoke(self, messages: Any, **kwargs) -> Any:
        """Invoke the LLM synchronously"""
        if isinstance(messages, List) and all(isinstance(msg, BaseMessage) for msg in messages):
            return self._generate(messages, **kwargs)
        else:
            raise ValueError("Input must be a list of BaseMessage")
    
    async def ainvoke(self, messages: Any, **kwargs) -> Any:
        """Invoke the LLM asynchronously, trả về AIMessage cho agent"""
        if isinstance(messages, list) and all(isinstance(msg, BaseMessage) for msg in messages):
            result = await self._agenerate(messages, **kwargs)
            text = result.generations[0][0].text if result.generations and result.generations[0] else ""
            return AIMessage(content=text)
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
        return "openai_llm"
    
# # Example usage
# if __name__ == "__main__":
#     import asyncio

#     async def main():
#         # Get API credentials from environment
#         api_key = os.getenv('OPENAI_API_KEY')
#         api_base = os.getenv('OPENAI_API_BASE', "https://api.openai.com")   
#         model_name = os.getenv('MODEL_NAME', "gpt-3.5-turbo")
        
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY environment variable not set")
        
#         # Initialize LLM
#         llm = OpenAILLM(
#             openai_api_key=api_key,
#             # openai_api_base=api_base,
#             model_name="gpt-4o-mini",
#         )
        
#         # Test messages
#         messages = [HumanMessage(content="Hello, how are you?")]
        
#         print("=" * 60)
#         print("Testing OpenAI LLM")
#         print("=" * 60)
#         print(f"\nInput: {messages[0].content}")
#         print(f"Model: {model_name}")
#         print(f"API Base: {api_base}\n")
        
#         try:
#             # Async invoke
#             response = await llm.ainvoke(messages)
#             print("Response:")
#             print(f"  Type: {type(response).__name__}")
#             print(f"  Content: {response.content}")
#             print("\n" + "=" * 60)
            
#         except Exception as e:
#             print(f"Error: {e}")
#             import traceback
#             traceback.print_exc()
    
#     asyncio.run(main())
