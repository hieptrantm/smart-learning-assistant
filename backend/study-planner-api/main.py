"""
main.py -- FastAPI application for the Study Planner service.
Lifespan pattern: init MCP client + agent at startup, cleanup at shutdown.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.controllers.planner_controller import router as planner_router
from app.config import APP_HOST, APP_PORT, MCP_URL
from app.database import Base, engine
from app import models  # noqa: F401
from app.llm.together_llm import TogetherLLM
from app.agents.study_planner_agent import StudyPlannerAgent
from app.services.planner_orchestrator import set_planner_agent
from app.services.qdrant_service import QdrantService  

from dotenv import load_dotenv
load_dotenv()

together_api_key = os.getenv("TOGETHER_API_KEY")
llm_model_id = os.getenv("LLM_MODEL_ID")

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global MCP tools reference
tools = []
qdrant_service = QdrantService() 

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, init MCP client, init agent. Shutdown: cleanup."""
    global tools

    # Create DB tables
    Base.metadata.create_all(bind=engine)

    # Connect to study-planner MCP server
    mcp_client = MultiServerMCPClient(
        {
            "study_planner": {
                "url": MCP_URL,
                "transport": "streamable_http",
            }
        }
    )
    tools = await mcp_client.get_tools()
    logger.info(f"Get MCP tools: {[tool.name for tool in tools]}")

    # Init LLM + agent with MCP tools
    llm_client = TogetherLLM(together_api_key=together_api_key, model_name=llm_model_id)
    planner = StudyPlannerAgent(llm_client, tools, qdrant_service)
    set_planner_agent(planner)

    yield

app = FastAPI(
    title="Study Planner Service",
    description="Manage subjects, generate AI study plans, sync with Google Calendar.",
    version="1.0.0",
    lifespan=lifespan,
    root_path="/planner",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planner_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "study-planner"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT)
