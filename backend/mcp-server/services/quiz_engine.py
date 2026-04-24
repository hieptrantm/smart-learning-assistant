from urllib import response

from llm.base import BaseLLM
from dotenv import load_dotenv
from typing import Dict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from config import get_prompts, quiz_type_mapping, quiz_format_mapping

import os

import json
import logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

prompts = get_prompts()

class QuizGenerationPipeline:
    """
    Generate quiz data from lecture content.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(QuizGenerationPipeline, cls).__new__(cls)
        return cls._instance

    def __init__(
            self,
            llm_client: BaseLLM
        ):
        if not QuizGenerationPipeline._initialized:
            self.llm_client = llm_client
            QuizGenerationPipeline._initialized = True
            
    # Helper function
    def parse_quiz_response(self, response: str) -> Dict:
        # Extract JSON part from the response
        start_idx = response.find('[')
        end_idx = response.rfind(']') + 1
        json_str = response[start_idx:end_idx]
        
        try:
            quiz_data = json.loads(json_str)
            return quiz_data
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}")
            return {}
            
    async def _llm_generate_from_data(self, **kwargs) -> str:
        """Generate lecture content from images and notes using LLM"""

        quiz_gen_sys_prompt = kwargs.get('quiz_gen_sys_prompt', '')
        # logger.info(f"Quiz generation system prompt: {quiz_gen_sys_prompt[:200]}...")  # Log the beginning of the prompt for debugging
        quiz_gen_user_prompt = kwargs.get('quiz_gen_user_prompt', '')
        # logger.info(f"Quiz generation user prompt: {quiz_gen_user_prompt[:200]}...")  # Log the beginning of the prompt for debugging
        messages = [
            SystemMessage(content=quiz_gen_sys_prompt),
            HumanMessage(content=[
                {"type": "text", "text": quiz_gen_user_prompt},
            ])
        ]
        
        response = await self.llm_client.ainvoke(messages)
        
        if hasattr(response, 'content'):
            content = response.content
        else:
            # LLMResult object
            content = response.generations[0][0].text if response.generations and response.generations[0] else ""
        # logger.info(f"LLM Response Detail: {content}")
        return content
    
    async def generate_quiz(self, data: str, title: str, quiz_request: Dict = None, previous_quizzes: str = ""):
        """Generate quiz from lecture content"""
        
        logger.info(f"Received quiz generation request with title: {title} and quiz_request: {quiz_request}")
        raw_question_types = quiz_request.get("question_type", ["multiple_choice"])
        # Normalize: flatten comma-separated strings inside the list
        if isinstance(raw_question_types, str):
            raw_question_types = [raw_question_types]
        question_types = []
        for qt in raw_question_types:
            question_types.extend([q.strip() for q in qt.split(",") if q.strip()])
        logger.info(f"Quiz question types requested: {question_types}")
        quiz_types_description = "\n - ".join([quiz_type_mapping.get(qt, "") for qt in question_types])
        quiz_format_description = ",\n".join([quiz_format_mapping.get(qt, "") for qt in question_types if qt in quiz_format_mapping])
        num_questions = quiz_request.get("num_questions", 5)
        quiz_request_formatted = {
            'num_types': len(question_types),
            "num_questions": num_questions,
            "quiz_type_description": quiz_types_description,
            "quiz_format_description": quiz_format_description
        }
        
        # logger.info(f"Request formatted before quiz generation: {quiz_request_formatted}")
        try:
            quiz_data = await self._llm_generate_from_data(
                quiz_gen_sys_prompt=prompts['system_quiz_gen_prompt'].format(
                    len_quiz_type=quiz_request_formatted['num_types'],
                    quiz_type_description=quiz_request_formatted['quiz_type_description'],
                    num_questions=quiz_request_formatted['num_questions'],
                    quiz_format=quiz_request_formatted['quiz_format_description'],
                    language="Vietnamese"
                ),
                quiz_gen_user_prompt=prompts['user_quiz_gen_prompt'].format(
                    title=title,
                    data=data,
                    previous_quizzes=previous_quizzes
                )
            )
        except Exception as e:
            logger.error(f"Error during quiz generation: {e}")
            raise Exception(f"Quiz generation failed: {e}") from e
        
        if quiz_data:
            parsed_quiz = self.parse_quiz_response(quiz_data)
            logger.info(f"Quiz data generated with {len(parsed_quiz)} questions.")
            return parsed_quiz  
        return None
        