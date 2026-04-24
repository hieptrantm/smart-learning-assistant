from langchain_core.messages import HumanMessage, SystemMessage
from typing import Annotated, Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import logging
import json
import time
import os
import uuid
from pydantic import Field

from services.quiz_engine import QuizGenerationPipeline
from llm.base import BaseLLM
from app_models.requests import ChatResponse, Question, GenerateQuizResponse
# from config import QA_PROMPT, SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class QuizGeneratorTool:
    """
    Tool for generating quiz questions from lesson content.
    """
    def __init__(self, llm_client: BaseLLM):
        self.llm_client = llm_client

    async def generate_quiz(
        self,
        title: Annotated[str, Field(..., description="The title of the quiz or lesson used to contextualize question generation")],
        description: Annotated[Optional[str], Field(default=None, description="Optional lesson content or description used to generate quiz questions")]=None,
        totalQuestions: Annotated[int, Field(default=10, description="The total number of quiz questions to generate")]=10,
        questions: Annotated[Optional[List[Question]], Field(default=None, description="An optional list of existing questions to preserve and extend during quiz generation")] = None,
    ) -> str:
        """
        Tool description: Generate a quiz test from lesson content and optionally extend an existing set of questions.
        """
        logger.info(f"Quiz generating with params: title={title}, description length={len(description) if description else 0}, totalQuestions={totalQuestions}, existing questions count={len(questions) if questions else 0}")
        logger.info(f"Quiz generation description: {description[:200] if description else 'No description provided'}...")
        
        # Types of questions for the quiz (multiple_choice, true_false, short_answer, fill_in_the_blank)
        pipeline = QuizGenerationPipeline(self.llm_client)

        question_types = [
            ["multiple_choice", "true_false"],
            ["short_answer", "fill_in_the_blank"]
        ]
        source_description = description or ""
        existing_questions = list(questions) if questions else []

        num_questions_batch1 = int(totalQuestions * 0.75)
        num_questions_batch2 = totalQuestions - num_questions_batch1

        # Chạy 2 batch song song — mỗi batch là một LLM call độc lập
        async def _run_batch(qtype: list, n: int, previous_context: str):
            quiz_input = {"num_questions": n, "question_type": qtype}
            logger.info(f"Starting quiz generation with parameters: {quiz_input}.")
            return await pipeline.generate_quiz(
                title=title,
                data=source_description,
                quiz_request=quiz_input,
                previous_quizzes=previous_context
            )

        previous_context = "\n".join(
            [f"Câu hỏi {i+1}: {q.get('text', '')}" for i, q in enumerate(existing_questions)]
        ) if existing_questions else ""

        try:
            batch1_result, batch2_result = await asyncio.gather(
                _run_batch(question_types[0], num_questions_batch1, previous_context),
                _run_batch(question_types[1], num_questions_batch2, previous_context),
            )
        except Exception as exc:
            raise Exception(f"Quiz generation failed: {exc}") from exc

        quiz_data = list(existing_questions)
        for result in (batch1_result, batch2_result):
            if isinstance(result, list):
                quiz_data.extend(result)
            else:
                quiz_data.append(result)

        if not quiz_data:
            raise Exception("Quiz generation returned no results.")

        logger.info(f"Quiz data generation successful with {len(quiz_data)} questions generated.")
        return json.dumps({
            "success": True,
            "tool_name": "generate_quiz",
            "content": "Tool generate quiz successful. The result has been displayed.",
            "query": source_description,
            "results_count": 1,
            "tool_result": quiz_data
        }, ensure_ascii=False, indent=2)
        
if __name__ == "__main__":
    # Example usage
    from llm.together_llm import TogetherLLM
    from config import TOGETHER_API_KEY, LLM_MODEL_ID, MCP_PORT, MCP_HOST
    
    llm_client = TogetherLLM(
        together_api_key=TOGETHER_API_KEY,
        model_name=LLM_MODEL_ID
    )
    quiz_tool = QuizGeneratorTool(llm_client)

    example_title = "Bài học về Lịch sử Việt Nam"
    example_description = "Nội dung bài học về lịch sử Việt Nam từ thời kỳ cổ đại đến hiện đại..."
    example_total_questions = 10

    loop = asyncio.get_event_loop()
    quiz_result = loop.run_until_complete(
        quiz_tool.generate_quiz(
            title=example_title,
            description=example_description,
            totalQuestions=example_total_questions
        )
    )
    print(quiz_result)