import logging
from typing import Dict
from langchain_core.messages import (
    HumanMessage
)

from config import get_prompts
from llm.base import BaseLLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

prompts = get_prompts()

class HistorySummarizationEngine:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new HistorySummarizationEngine instance")
            cls._instance = super(HistorySummarizationEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self, llm_client: BaseLLM):
        self.llm_client = llm_client
        if not self._initialized:
            self.__class__._initialized = True
            logger.info("Initialized HistorySummarizationEngine")

    def summarize(
        self,
        conversation_text: str,
    ) -> Dict:
        logger.info("Summarizing conversation text")

        if not conversation_text or not conversation_text.strip():
            logger.info("Empty conversation text, nothing to summarize")
            return {"summary": "Không có lịch sử hội thoại."}
        
        # logger.info(f"Formatted chat history:\n{formatted_history}")
        # logger.info(f"Lecture content for summary:\n{self.lecture_content}")

        prompt = prompts["history_summarize_prompt"].format(conversation_text=conversation_text)
        logger.info("Calling LLM to generate conversation summary")
        try:
            response = self.llm_client._generate(
                messages=[HumanMessage(prompt + "/no_think")]
            )
            summary = response.generations[0][0].text.strip()
            # logger.info(f"Generated summary:\n{summary}")

            return {
                "prompt": prompt + "/no_think",
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {"summary": "Lỗi khi tóm tắt lịch sử hội thoại."}

    async def asummarize(
        self,
        conversation_text: str,
    ) -> Dict:
        """Async version of summarize - avoids blocking the event loop."""
        if not conversation_text or not conversation_text.strip():
            return {"summary": "Không có lịch sử hội thoại."}

        prompt = prompts["history_summarize_prompt"].format(conversation_text=conversation_text)
        try:
            result = await self.llm_client._agenerate(
                messages=[HumanMessage(prompt + "/no_think")]
            )
            summary = result.generations[0][0].text.strip()
            return {"prompt": prompt + "/no_think", "summary": summary}
        except Exception as e:
            logger.error(f"Error generating async summary: {e}")
            return {"summary": "Lỗi khi tóm tắt lịch sử hội thoại."}
