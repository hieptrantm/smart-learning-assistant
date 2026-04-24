"""
llm_client.py – Singleton LLM client factory.
"""

from langchain_together import ChatTogether
from app.config import TOGETHER_API_KEY, LLM_MODEL


def create_llm_client() -> ChatTogether:
    """Create a ChatTogether LLM client instance."""
    return ChatTogether(
        model=LLM_MODEL,
        together_api_key=TOGETHER_API_KEY,
        temperature=0.3,
        max_tokens=4096,
    )


