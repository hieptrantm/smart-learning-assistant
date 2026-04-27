from app.utils.plan_generator import PlanGenerator
from app.llm.together_llm import TogetherLLM
from dotenv import load_dotenv
load_dotenv()

import os

LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "gpt-4")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

llm_client = TogetherLLM(together_api_key=TOGETHER_API_KEY, model_name=LLM_MODEL_ID)
plan_generator = PlanGenerator(llm_client=llm_client)

import asyncio

sessions =  asyncio.run(plan_generator.generate(
    db_url="postgresql://postgres:postgres@localhost:5432/authdb",
    subject_id=36,
    subject_name="cổ tích",
    end_date_str="2026-05-02",
    checkpoint_node_id=None
))

for session in sessions:
    print(session)