"""
mcp_server.py -- Study Planner MCP server.
Exposes build_schedule and send_email tools via FastMCP.
"""

import logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import config
from tools.calendar_tool import BuildScheduleTool
from tools.email_tool import SendEmailTool
from llm.together_llm import TogetherLLM
from config import TOGETHER_API_KEY, LLM_MODEL_ID, MCP_PORT, MCP_HOST
from vectordb.engine import VectorDBEngine
from graph_db.engine import GraphDBEngine
from tools.lightrag_retrieval import LightRAGRetrieval
from tools.gen_quiz import QuizGeneratorTool

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm_client = TogetherLLM(
    together_api_key=TOGETHER_API_KEY,
    model_name=LLM_MODEL_ID
)
vectordb_engine = VectorDBEngine()
graphdb_engine = GraphDBEngine()

# Initialize tool instances (singleton)
calendar_tool = BuildScheduleTool()
email_tool = SendEmailTool()
retrieval = LightRAGRetrieval(
    llm_client=llm_client,
    vectordb_engine=vectordb_engine,
    graphdb_engine=graphdb_engine
)
quiz_generator = QuizGeneratorTool(llm_client)

# Initialize MCP server
mcp_server = FastMCP("StudyPlannerTools", port=MCP_PORT, host=MCP_HOST)
mcp_server.add_tool(calendar_tool.build_one_schedule)
mcp_server.add_tool(email_tool.send_email)
mcp_server.add_tool(retrieval.retrieve)
mcp_server.add_tool(quiz_generator.generate_quiz)
if __name__ == "__main__":
    mcp_server.run(transport="streamable-http")
