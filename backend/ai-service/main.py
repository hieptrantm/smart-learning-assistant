from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
import uvicorn
import json
import time
import os
import uuid
import asyncio
import logging
import sys
from langchain_mcp_adapters.client import BaseTool, MultiServerMCPClient
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from llm.openai_llm import OpenAILLM
from app_models.requests import Message, ChatRequest, ChatResponse, Question
from db.db_utils import add_message, get_messages
from llm_chatbot.normal_agent import TutorAgent
from history_summarization.engine import HistorySummarizationEngine
from config import get_prompts

# Configure logging globally BEFORE any logging is used
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("="*60)
logger.info("FastAPI Server Starting - Logging System Initialized")
logger.info("="*60)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_ID = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
llm_client = OpenAILLM(openai_api_key=OPENAI_API_KEY, model_name=MODEL_ID)
history_summarization_engine = HistorySummarizationEngine(llm_client=llm_client)

tools: List[BaseTool] = []
mcp_host = os.getenv("MCP_HOST", "localhost")
mcp_port = os.getenv("MCP_PORT", "8030")
logger.info(f"Configured MCP host: {mcp_host}, port: {mcp_port}")

prompts = get_prompts()
explain_system_prompt = prompts.get("explain_system_prompt", "")
explain_qa_prompt = prompts.get("explain_qa_prompt", "")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tools
    try:
        mcp_client = MultiServerMCPClient(
            {
                "itsm": {
                    "url": f"http://{mcp_host}:{mcp_port}/mcp",
                    "transport": "streamable_http",
                }
            }
        )
        tools = await mcp_client.get_tools()
        # Filter to user only retrieve tool
        tools = [tool for tool in tools if tool.name in ["retrieve", "generate_quiz"]]
    except Exception as e:
        logger.error(f"Error connecting to MCP server at {mcp_host}:{mcp_port} - {e}")
        tools = []
    logger.info(f"Loaded {len(tools)} MCP tools: {[t.name for t in tools]}")
    # logger.info(f"Detail of tools: {tools}")
    yield


app = FastAPI(title="Teacher Assistant Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# session = get_session()
    
def parse_history_messages(messages: List[Message], n_last_user_messages: int = 3):
    history: List[BaseMessage] = []
    last_user_message = ""

    for msg in messages[-n_last_user_messages:]:  # Only take the last N messages for context
        # Use dict-style access for RealDictRow
        role = msg["role"] if isinstance(msg, dict) or hasattr(msg, "__getitem__") else getattr(msg, "role", None)
        content = msg["content"] if isinstance(msg, dict) or hasattr(msg, "__getitem__") else getattr(msg, "content", None)

        if role == "system":
            history.append(SystemMessage(content=content))
        elif role == "user":
            last_user_message = content
            # Only add previous user turns to history; the last one is the question
            if msg is not messages[-1]:
                history.append(HumanMessage(content=content))
        elif role == "assistant":
            history.append(AIMessage(content=content))

    # Make sure the last user message is not duplicated in history
    if history and isinstance(history[-1], HumanMessage):
        history = history[:-1]
        
    logger.info(f"History messsages parsed: {history}")

    return history, last_user_message

@app.post("/v1/chat/completions/stream", response_model=ChatResponse)
async def assistant_chat_completions(request: ChatRequest):
    # Nếu data request chứa thông tin của lịch sử chat -> trả về response
    
    logger.info(f"All chat request data: {request}")
    question = request.question
    subject_id = request.subject_id
    logger.info(f"Received chat request - subject_id: {subject_id}, question: '{question[:120]}'")
    
    if request.user_id and request.subject_id:
        history_messages = get_messages(subject_id=request.subject_id)
        logger.info(f"Retrieved {len(history_messages)} messages from subject_id={request.subject_id} for user_id={request.user_id}")
        
    
    history, last_user_message = parse_history_messages(history_messages or [])
    
    last_user_message = question
    
    logger.info(f"Parsed history into {len(history)} messages. Last user message: '{last_user_message[:120]}'")
    
    if not question:
        raise HTTPException(status_code=400, detail="No user message found.")

	# streaming response
    if request.stream:
        async def generate():
            session_id = str(uuid.uuid4())
            logger.info(f"[{session_id}] question: {question[:120]}")
            try:
                agent = await TutorAgent.create(
                    llm=llm_client,
                    tools=tools,
                    history_summarization_engine=history_summarization_engine,
                    subject_id=subject_id,
                    lecture_title=request.lecture_title,
                    lecture_content=request.lecture_content,
                )

                try:
                    keep_alive_active = True
                    completed_response = ""
                    
                    async def keep_alive():
                        while keep_alive_active:
                            try:
                                yield "data: " + json.dumps({"type": "thinking", "content": "Reasoning..."}) + '\n\n'
                                await asyncio.sleep(15)
                            except asyncio.CancelledError:
                                break
                    loop = asyncio.get_running_loop()
                    gen_future: asyncio.Future = loop.create_future()
                    tool_event_queue: asyncio.Queue = asyncio.Queue()
                    keeps_alive_generator = keep_alive()
                    keep_alive_task = None
                    
                    def callback_text_generate(gen_async_iter):
                        if not gen_future.done():
                            gen_future.set_result(gen_async_iter)
                    agent.callback_text_generate = callback_text_generate
                    
                    # Start the agent in a background task
                    async def run_agent():
                        prev_tool_count = 0
                        async for state in agent.stream(
                            question,
                            session_id=session_id,
                            chat_history=history,
                        ):
                            if isinstance(state, dict):
                                current_results = state.get("tool_results", [])
                                if len(current_results) > prev_tool_count:
                                    for tool_res in current_results[prev_tool_count:]:
                                        await tool_event_queue.put(tool_res)
                                    prev_tool_count = len(current_results)
                    agent_task = asyncio.create_task(run_agent())
                    
                    try:
                        while not gen_future.done() and not agent_task.done():
                            if keep_alive_task is None or keep_alive_task.done():
                                keep_alive_task = asyncio.create_task(keeps_alive_generator.__anext__())
                                
                            done, pending = await asyncio.wait(
                                [keep_alive_task, gen_future, agent_task],
                                return_when=asyncio.FIRST_COMPLETED,
                                timeout=1.0
                            )
                            
                            if keep_alive_task in done and not gen_future.done():
                                try:
                                    chunk = await keep_alive_task
                                    logger.info(f"[{session_id}] sending keep-alive chunk: {str(chunk)}")
                                    yield chunk
                                    keep_alive_task = None
                                except StopAsyncIteration:
                                    break
                                except asyncio.CancelledError:
                                    break

                            # Drain tool results that arrived during this iteration
                            while not tool_event_queue.empty():
                                tool_res = tool_event_queue.get_nowait()
                                yield "data: " + json.dumps(
                                    {
                                        "type": "tool_result",
                                        "tool_name": tool_res.get("tool_name"),
                                        "success": tool_res.get("success"),
                                        "result": tool_res.get("result"),
                                    },
                                    ensure_ascii=False,
                                    default=str,
                                ) + '\n\n'
                    except asyncio.TimeoutError:
                            pass
                        
                    keep_alive_active = False
                    
                    if keep_alive_task is not None:
                        if not keep_alive_task.done():
                            keep_alive_task.cancel()
                        try:
                            await keep_alive_task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.debug(f"[{session_id}] keep-alive task error during cancellation: {e}")
                            
                    # Clear keep-alive generator
                    try:
                        await keeps_alive_generator.aclose()
                    except Exception as e:
                        logger.debug(f"[{session_id}] keep-alive generator error during aclose: {e}")
                        
                    if gen_future.done() and not gen_future.exception():
                        gen = gen_future.result()
                        try:
                            async for token in gen:
                                completed_response += token
                                yield "data: " + json.dumps({"type": "token", "content": token}, ensure_ascii=False) + '\n\n'
                                await asyncio.sleep(0)
                        except Exception as e:
                            logger.error(f"[{session_id}] error while streaming tokens: {e}")
                            yield "data: " + json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + '\n\n'
                    
                    # Summarize the full response and add to history
                    if question:
                            add_message(
                                subject_id=request.subject_id,
                                user_id=request.user_id,
                                content=question,
                                role='user'
                            )
                    if completed_response and request.user_id and request.subject_id:
                        add_message(
                            subject_id=request.subject_id,
                            user_id=request.user_id,
                            content=completed_response,
                            role='assistant')
                except Exception as e:
                    yield "data: " + json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + '\n\n'
                    return

                # yield "data: " + json.dumps({"type": "completed response", "content": completed_response}, ensure_ascii=False) + '\n\n'
                yield "data: [DONE]\n\n"
                logger.info(f"[{session_id}] stream complete")

            except asyncio.CancelledError:
                logger.info(f"[{session_id}] client disconnected") 
                raise
            except Exception as e:
                logger.exception(f"[{session_id}] error during stream")
                error_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # non-streaming response
    session_id = str(uuid.uuid4())
    logger.info(f"[{session_id}] non-stream question: {question[:120]}")

    try:
        agent = await TutorAgent.create(
            llm=llm_client,
            tools=tools,
        )

        full_reply = ""
        async for token in agent.stream(
            message=question,
            session_id=session_id,
            chat_history=history,
        ):
            if token:
                full_reply += token

        return ChatResponse(
            id=session_id,
            reply=full_reply,
            created=int(time.time()),
        )

    except Exception as e:
        logger.exception(f"[{session_id}] error in non-stream mode")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/assistant/explain-answer", response_model=ChatResponse)
async def explain(quiz_question: Question, actual_answer: str, user_question: str = ""):

    session_id = str(uuid.uuid4())
    llm_messages = [
        SystemMessage(content=explain_system_prompt),
        HumanMessage(	
            content=explain_qa_prompt.format(   
                quiz_question=json.dumps(quiz_question.model_dump()),
                actual_answer=actual_answer,
                user_question=user_question,
            )		
        ),
    ]
    logger.info("[%s] incoming question: %s", session_id, user_question[:120])

    try:
        response = await llm_client.ainvoke(llm_messages)
        return ChatResponse(
            id=session_id,
            reply=response.content,
            created=int(time.time()),
        )
    except Exception as exc:
        logger.exception("[%s] error in non-stream mode", session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8111)