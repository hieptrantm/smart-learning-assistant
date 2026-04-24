import asyncio, json, logging, os, re, sys, time, uuid
from typing import Any, Dict, List, Optional, TypedDict, Callable
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langchain_mcp_adapters.client import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage
)

from config import get_prompts, format_tools_description
from history_summarization.engine import HistorySummarizationEngine
from llm.base import BaseLLM
from .base_agent import BaseLangGraphAgent

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
prompts = get_prompts()

class AgentStateDict(TypedDict):
    """Type definition for agent state dictionary"""

    messages: List[BaseMessage]
    current_step: str
    error: Optional[str]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    session_id: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]
    config: RunnableConfig
    iteration_count: int
    response: Optional[str] 

class TutorAgent(BaseLangGraphAgent):
    """
    LangGraph-based agent implementation
    """

    SUPPORTED_CONTENT_TYPES = ["text/plain", "application/json"]

    def __init__(
        self,
        # reflection_engine: ReflectionEngine = None,
        llm: BaseLLM = None,
        together_llm: BaseLLM = None,
        tools: Optional[List[BaseTool]] = None,
        subject_id: Optional[str] = None,
        lecture_title: Optional[str] = "",
        lecture_content: Optional[str] = "",
        history_summarization_engine: Optional[HistorySummarizationEngine] = None,
        system_prompt: str = prompts['system_normal_prompt'],
        qa_prompt: str = prompts['qa_prompt_agent'],
        callback_text_generate: Optional[Callable] = None,
        chat_history: Optional[List[BaseMessage]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            state_dict_type=AgentStateDict,
            tools=tools,
            callback_text_generate=callback_text_generate,
            *args,
            **kwargs,
        )
        # self.reflection_engine = reflection_engine
        self.llm = llm
        self.together_llm = together_llm
        self.history_summarization_engine = history_summarization_engine
        self.system_prompt = system_prompt
        self.qa_prompt = qa_prompt
        self._stream_tasks: Dict[str, asyncio.Task] = {}
        self.llm_calls = {}
        self.token_queues: Dict[str, asyncio.Queue] = {}  # Queue for streaming tokens
        self.chat_history = chat_history or []  # Store full chat history for context
        self.subject_id = subject_id
        self.lecture_title = lecture_title or ""
        self.lecture_content = lecture_content or ""
        logger.debug(f"Chat history initialized with {len(self.chat_history)} messages")
    
    @classmethod
    async def create(
        cls,
        # reflection_engine: ReflectionEngine = None,
        llm: Any = None,
        together_llm: BaseLLM = None,
        tools: Optional[List[BaseTool]] = None,
        history_summarization_engine: Optional[HistorySummarizationEngine] = None,
        subject_id: Optional[str] = None,
        lecture_title: Optional[str] = "",
        lecture_content: Optional[str] = "",
        system_prompt: str = prompts['system_normal_prompt'],
        qa_prompt: str = prompts['qa_prompt_agent'],
        callback_text_generate: Optional[Callable] = None,
        store: Optional[AsyncPostgresStore] = None,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        chat_history: Optional[List[BaseMessage]] = None,
        *args,
        **kwargs,
    ):
        """Create an instance of TutorAgent"""
        instance = cls(
            llm=llm,
            together_llm=together_llm,
            tools=tools,
            history_summarization_engine=history_summarization_engine,
            system_prompt=system_prompt,
            qa_prompt=qa_prompt,
            callback_text_generate=callback_text_generate,
            chat_history=chat_history,
            subject_id=subject_id,
            lecture_title=lecture_title,
            lecture_content=lecture_content,
            *args,
            **kwargs,
        )
        await instance._async_init(store, checkpointer)
        return instance
    def _setup_graph(self):
        """Setup the LangGraph workflow"""

        # Initialize the state graph
        self.workflow = StateGraph(AgentStateDict)

        # Add nodes
        self.workflow.add_node("llm", self._llm_node)
        self.workflow.add_node("tools", self._tools_node)
        self.workflow.add_node("final", self._final_node)

        # Set entry point
        self.workflow.set_entry_point("llm")

        # Add conditional edges
        self.workflow.add_conditional_edges(
            "llm", self._should_continue, {"llm": "llm", "tools": "tools", "final": "final", "end": END}
        )
        
        self.workflow.add_conditional_edges(
            "final", self._should_continue, {"end": END}
        )

        self.workflow.add_conditional_edges(
            "tools", self._should_continue, {"llm": "llm", "end": END}
        )

        # Compile the graph
        self.graph = self.workflow.compile(checkpointer=self.checkpointer, store=self.store)

    def _bump_and_maybe_finalize(self, state: AgentStateDict, limit: int = 3) -> None:
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        if state["iteration_count"] > limit and state.get("current_step") != "final":
            state["current_step"] = "final"

    async def _llm_node(self, state: AgentStateDict) -> AgentStateDict:
        # Start timing
        start_time = time.time()
        node_name = "llm_node"
        session_id = state.get("session_id", "unknown")
        subject_id = state.get("subject_id", "unknown")
        
        logger.info(f"[{session_id}][{subject_id}] Starting {node_name} execution")
        
        try:
            # Get the last message
            messages = state["messages"][-5:]
            logger.info(f"[{session_id}][{subject_id}] Total messages in state: {len(messages)}")
            logger.info(f"[{session_id}][{subject_id}] Messages detail: {messages}")
            for msg in messages:
                logger.info(f"[{session_id}][{subject_id}] Message type: {type(msg).__name__}, content: {str(msg.content)[:100]}...")
            if not messages:
                return state

            last_message = messages[-1]
            logger.info(f"[LLM NODE][{session_id}][{subject_id}] Last message type: {type(last_message).__name__}")

            # Only process if this is not a system message
            if isinstance(last_message, SystemMessage):
                return state

            # Create messages for LLM: system message + all previous messages + current formatted message
            llm_messages: List[BaseMessage] = []

            # Extract content from the message
            message_content = str(last_message.content)

            # Aggregate context from previous messages and tool results in chronological order
            context_steps = []

            # Process messages and tool results in chronological order
            for _, msg in enumerate(messages):
                if isinstance(msg, HumanMessage):
                    message_content = msg.content
                    context_steps.append(f"User: {msg.content}")
                else:
                    context_steps.append(f"Assistant: {msg.content}")
                    
            tools_context = state.get("tool_results", [])    
            last_tool_result = tools_context[-1] if tools_context else None
            # logger.info(f"Last tool result: {last_tool_result}")
            tools_context_str = ""
            if last_tool_result:
                tools_context_str = f"""
Đã gọi tool: {last_tool_result.get("tool_name", "")}
Trạng thái: {last_tool_result.get("success", "")}
Kết quả: {last_tool_result.get("result", "")}
                """

            # Combine all context steps
            aggregated_context = (
                "\n".join(context_steps)
                if context_steps
                else "No previous context available."
            )
            logger.info(f"[LLM NODE][{session_id}] Aggregated context before summarization: {aggregated_context[:800]}...")
            
            logger.info(f"[LLM NODE][{session_id}] history messages: {len(messages)}")
            # Summarize conversation history using HistorySummarizationEngine
            # Use self.chat_history (full external history from HTTP request), not state["messages"]
            # external_history = self.chat_history if hasattr(self, 'chat_history') and self.chat_history else []
            # logger.debug(f"[{session_id}] External history length: {len(external_history)}")
            if self.history_summarization_engine:
                try:
                    logger.info(f"[LLM NODE][{session_id}] Summarizing messages")
                    logger.debug(f"[{session_id}] Aggregated context before summarization: {aggregated_context[:800]}...")
                    summary_result = await self.history_summarization_engine.asummarize(aggregated_context)
                    # logger.debug(f"[{session_id}] History summarization result: {summary_result}")
                    aggregated_context = summary_result.get("summary", "No previous context available.")
                    # logger.info(f"[LLM NODE][{session_id}] History summary: {aggregated_context[:200]}...")
                except Exception as e:
                    logger.error(f"[LLM NODE][{session_id}] Error summarizing history: {e}")
                    aggregated_context = "No previous context available."
            else:
                aggregated_context = "No previous context available."
                logger.info(f"[LLM NODE][{session_id}] No external history to summarize, using default context.")
        
            # logger.info(f"[LLM NODE][{session_id}] Aggregated context: {aggregated_context[:800]}...")
            
            logger.info(f"[TOOL NODE][{session_id}] Number of tools available: {len(self.tools)}")
            
            # Create system prompt
            try:
                tool_description = format_tools_description(self.tools)
                # logger.info(f"[LLM NODE][{session_id}] Tool descriptions: {tool_description}")
                system_prompt = self.system_prompt.format(
                    tool_descriptions=tool_description
                )
                
                logger.info(f"[LLM NODE][{session_id}] System prompt created successfully: \n{system_prompt}")
            except Exception as e:
                logger.error(f"[LLM NODE][{session_id}] Error formatting system prompt: {e}")
                system_prompt = self.system_prompt.format(tool_descriptions="")
            
            # Create messages for LLM: system message + all previous messages + current formatted message
            llm_messages.insert(0, SystemMessage(content=system_prompt))

            # Create qa prompt
            qa_prompt = self.qa_prompt.format(
                request=message_content,
                history=aggregated_context,
                tool_results=tools_context_str,
                subject_id=self.subject_id,
                lecture_title=self.lecture_title or "Không có",
                lecture_content=self.lecture_content or "Không có"
            )
            logger.info(f"[LLM NODE][{session_id}] QA prompt: {qa_prompt}...")
            # Add the current message formatted with QA prompt
            llm_messages.append(HumanMessage(content=qa_prompt))
            
            # Log LLM invocation start
            llm_start_time = time.time()
            logger.info(f"[{session_id}] Starting LLM invocation in {node_name}")
            
            # Get response from LLM
            try:
                response = await self.llm.ainvoke(llm_messages)
                response_content = response.content
                
                self.llm_calls[session_id][state["iteration_count"]] = {
                    "system_prompt": system_prompt,
                    "message": message_content,
                    "qa_prompt": qa_prompt,
                    "response": response_content,
                }
            except Exception as e:
                logger.error(f"Error during LLM invocation: {e}")
                response_content = f"Error during LLM invocation: {e}"
                self.llm_calls[session_id][state["iteration_count"]] = {
                    "system_prompt": system_prompt,
                    "message": message_content,
                    "qa_prompt": qa_prompt,
                    "response": response_content,
                }
            
            # Log LLM invocation end
            llm_end_time = time.time()
            llm_duration = llm_end_time - llm_start_time
            logger.info(f"[{session_id}] LLM invocation completed in {node_name}: {llm_duration:.2f}s")
            logger.info(f"[LLM NODE][{session_id}] Response: {response_content}")
            
            # Try to extract tool call from response
            tool_call = self._extract_tool_call(response_content)
            logger.info(f"Extracted tool call: {tool_call}")
            if tool_call:
                # Add reasoning to state
                tool_name = tool_call.get("tool_name", "")
                tool_params = tool_call.get("arguments", {})
                
                # # Mock params for calling
                # tool_params = {
                #     'title': 'Nguyên tử',
                #     'subject': 'khtn7',
                #     'class_name': 'lop7',
                #     'user_prompt': 'Hãy tạo một bài giảng ngắn về nguyên tử cho học sinh lớp 7, môn khoa học tự nhiên, sử dụng nội dung từ sách giáo khoa và các hình ảnh liên quan.'
                # }
                
                reasoning = tool_call.get("reasoning", response_content)
                state["messages"].append(
                    AIMessage(content=f"Call to tool {tool_name} with reason: '{reasoning}' and parameters: '{tool_params}'")
                )
                # Add tool call to state
                state["tool_calls"].append(
                    {
                        "tool_name": tool_name,
                        "tool_call_id": str(uuid.uuid4()),
                        "parameters": tool_params,
                        "timestamp": datetime.now(),
                    }
                )
                state["current_step"] = "tools"
                return state            
            if response_content is not None:
                logger.info(f"No tool call extracted from LLM response, moving to final node.")
                state["response"] = response_content
                state["current_step"] = "final"
                return state
            else:
                state["response"] = "LLM did not return any content."
                state["current_step"] = "final"
                return state

        except Exception as e:
            self.logger.error(f"Error in llm node: {e}")
            state["error"] = str(e)
            state["current_step"] = "end"
            return state
        
        finally:
            if state.get("current_step") not in ("end", "final"):
                self._bump_and_maybe_finalize(state, limit=3)
            
            # End timing and log
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[{session_id}] Completed {node_name} execution: {duration:.2f}s")


    def _extract_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        # Lấy nội dung trong @@CALL_TOOL@@ ... @@END@@
        match = re.search(r'@@CALL_TOOL@@\s*(.*?)@@END@@', response, re.DOTALL)
        if not match:
            return None

        body = match.group(1)

        name_match = re.search(r'tool_name:\s*(\S+)', body)
        args_match = re.search(r'arguments:\s*(\{.*\})', body, re.DOTALL)

        if not name_match or not args_match:
            return None

        try:
            arguments = json.loads(args_match.group(1))
        except json.JSONDecodeError:
            return None

        return {
            "tool_name": name_match.group(1).strip(),
            "arguments": arguments
        }

    async def _tools_node(self, state: AgentStateDict) -> AgentStateDict:
        """Tools node that executes tools"""
        # Start timing
        start_time = time.time()
        node_name = "tools_node"
        session_id = state.get("session_id", "unknown")
        
        logger.info(f"[{session_id}] Starting {node_name} execution")
        logger.debug(f"[{session_id}] State at start of tools node: {state}")
        # time.sleep(50)
        try:
            # Get the last tool call
            tool_calls = state["tool_calls"]
            if not tool_calls:
                logger.warning(f"[{session_id}] No pending tool calls. Ending tools node to avoid loop.")
                state["error"] = state.get("error") or "No pending tool calls"
                state["current_step"] = "final"
                return state

            last_tool_call = tool_calls[-1]
            last_tool_name = last_tool_call["tool_name"]
            last_parameters = last_tool_call["parameters"]
            last_tool_call_id = last_tool_call["tool_call_id"]
            logger.info(f"[TOOL NODE] Last tool: {last_tool_name}, params: {last_parameters}")
            logger.info(f"[{session_id}] Executing tool: {last_tool_name}")

            # Find and execute the tool
            tool_result = None
            tool_execution_start = time.time()

            # # Ensure that the agent does not call the same tool twice in a row
            # pre_tool_call = None
            # pre_tool_name = None 
            # pre_parameters = None
            # if len(tool_calls) >= 2:
            #     pre_tool_call = tool_calls[-2]
            #     pre_tool_name = pre_tool_call["tool_name"]
            #     pre_parameters = pre_tool_call["parameters"]
            #     logger.info(f"[TOOL NODE] Previous tool: {pre_tool_name}, params: {pre_parameters}")
            # if last_tool_name == pre_tool_name and last_parameters == pre_parameters:
            #     logger.warning(f"[{session_id}] Tool {last_tool_name} has been called!!!")
            #     tool_result = {
            #             "tool_name": last_tool_name,
            #             "result": f"Tool {last_tool_name} has called, please execute other tools",
            #             "success": None,
            #             "error": f"Tool {last_tool_name} has called, please execute other tools",
            #             "timestamp": datetime.now(),
            #             "tool_call_id": last_tool_call_id
            #         }
            # else:
            for tool in self.tools:
                if tool.name == last_tool_name:
                    logger.info(f"[{session_id}] Found tool {last_tool_name}, executing with parameters: {last_parameters}")
                    # Execute the tool
                    try:
                        result = (await tool.ainvoke(last_parameters))
                        # logger.info(f"[{session_id}] Tool {last_tool_name} executed successfully with result: {result}")
                    except Exception as e:
                        logger.error(f"[{session_id}] Error executing tool {last_tool_name}: {e}")
                        result = {
                            "content": None,
                            "success": False,
                            "error": str(e)
                        }
                    logger.debug(f"[{session_id}] Raw tool result: {result}")
                    try:
                        if isinstance(result, str):
                            result = json.loads(result)
                        elif not isinstance(result, dict):
                            result = {"content": str(result), "success": True, "error": None}
                        logger.info(f"[{session_id}] Tool {last_tool_name} execution result (parsed): {result.get('success')}")
                    except json.JSONDecodeError as e:
                        logger.error(f"[{session_id}] Error parsing tool result: {e}")
                        logger.debug(f"[{session_id}] debug Tool result: {result}")
                        result = {
                            "content": result if result else "Empty result from tool",
                            "success": bool(result),
                            "error": None if result else "Tool returned empty result"
                        }
                    
                    
                    tool_execution_end = time.time()
                    tool_execution_duration = tool_execution_end - tool_execution_start
                    logger.info(f"[{session_id}] Tool {last_tool_name} execution completed: {tool_execution_duration:.2f}s")
                    
                    try:
                        tool_result = {
                            "tool_name": last_tool_name,
                            "message": f"Tool executed with parameters: {last_parameters}",
                            "result": result.get("tool_result"),
                            "success": result.get("success"),
                            "error": result.get("error") if not result.get("success") else None,
                            "timestamp": datetime.now(),
                            "tool_call_id": last_tool_call_id
                        }
                    except Exception as e:
                        logger.error(f"[{session_id}] Error constructing tool result: {e}")
                        tool_result = {
                            "tool_name": last_tool_name,
                            "message": f"Tool executed with parameters: {last_parameters}",
                            "result": str(result),
                            "success": True,
                            "error": None,
                            "timestamp": datetime.now(),
                            "tool_call_id": last_tool_call_id
                        }
                    break

            if tool_result:
                state["tool_results"].append(tool_result)

                # Add tool result as an AI message
                if tool_result["success"]:
                    result_message = f"Tool {last_tool_name} executed response: {tool_result['result']}"
                else:
                    result_message = f"Tool {last_tool_name} failed: {tool_result['error']}"

                state["messages"].append(
                    ToolMessage(
                        content=f"Tool {last_tool_name} executed successfully", tool_call_id=last_tool_call_id
                    )
                )
                # Go back to LLM for reasoning
                state["current_step"] = "llm"
            else:
                # Tool not found
                error_message = f"Tool '{last_tool_name}' not found"
                state["messages"].append(
                    ToolMessage(
                        content=error_message, tool_call_id=last_tool_call_id
                    )
                )
                state["error"] = error_message
                state["current_step"] = "llm"

            return state

        except Exception as e:
            self.logger.error(f"[{session_id}] Error in tools node: {e}")
            state["error"] = str(e)
            state["current_step"] = "llm"
            return state
        
        finally:
            # End timing and log
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[{session_id}] Completed {node_name} execution: {duration:.2f}s")
        
    async def _final_node(self, state: AgentStateDict) -> AgentStateDict:
        """Finalization node that handles end of workflow"""
        # Start timing
        start_time = time.time()
        node_name = "final_node"
        session_id = state.get("session_id", "unknown")
        
        logger.info(f"[{session_id}] Starting {node_name} execution")
        logger.debug(f"[{session_id}] State at start of final node: {state}")
        
        try:
            # Get the last message
            messages = state["messages"]
            if not messages:
                return state

            last_message = messages[-1]
            logger.debug(f"[{session_id}] Last message at start of final node: {last_message}")

            # Only process if this is not a system message
            if isinstance(last_message, SystemMessage):
                return state
            # Extract content from the message
            message_content = str(last_message.content)
            # logger.info(f"[FINAL NODE] Last message content: {message_content}")
            
            # Get the last response
            response_content = state.get("response", "")
            
            # # Aggregate context from previous messages and tool results in chronological order
            context_steps = []

            # Process messages and tool results in chronological order
            for i, msg in enumerate(messages):
                if isinstance(msg, HumanMessage):
                    message_content = msg.content
                    context_steps.append(f"User: {msg.content}")
                elif isinstance(msg, ToolMessage):
                    context_steps.append(f"Tool Call: {msg.content}")
                else:
                    context_steps.append(f"Assistant: {msg.content}")

            # Combine all context steps
            aggregated_context = (
                "\n".join(context_steps)
                if context_steps
                else "No previous context available."
            )
            logger.info(f"[FINAL NODE][{session_id}] Aggregated context length: {len(aggregated_context)}")

            # Create system prompt
            final_system_prompt = prompts['system_final_prompt']
            final_qa_prompt = prompts['qa_final_prompt']
            
            # Create messages for LLM: system message + all previous messages + current formatted message
            llm_messages: List[BaseMessage] = []
            
            # Create messages for LLM: system message + all previous messages + current formatted message
            llm_messages.insert(0, SystemMessage(content=final_system_prompt))

            # Create QA prompt for the current message
            try:
                final_qa_prompt = final_qa_prompt.format(
                    raw_answer=response_content
                )
            except Exception as e:
                logger.error(f"Error formatting QA prompt: {e}")
                final_qa_prompt = final_qa_prompt.format(
                    raw_answer=response_content
                )
            
            self.llm_calls[session_id]["final"] = {
                "system_prompt": final_system_prompt,
                "message": message_content,
                "qa_prompt": final_qa_prompt,
                "response": "",
            }
            # Add the current message formatted with QA prompt
            llm_messages.append(HumanMessage(content=final_qa_prompt))
            # logger.info(f"[FINAL NODE] LLM Messages: {llm_messages}")
            logger.info(f"[FINAL NODE][{session_id}] Starting LLM stream...")
            logger.debug(f"[{session_id}] Final QA prompt: {final_qa_prompt}")

            response_content = ""
            chunk_count = 0
            gen = self.llm.astream(llm_messages)

            if self.callback_text_generate:
                self.callback_text_generate(gen)
                logger.info(f"[FINAL NODE][{session_id}] Streaming generator sent to callback")
            else:
                async for chunk in gen:
                    logger.info(f"[FINAL NODE][{session_id}] Received chunk: '{chunk}'")
                    chunk_count += 1
                    response_content += chunk

                logger.info(
                    f"[FINAL NODE][{session_id}] Stream completed. Total chunks: {chunk_count}, Content length: {len(response_content)}"
                )

            if response_content:
                state["messages"].append(AIMessage(content=response_content))
            # Chuyển sang node phân tích mức độ hiểu bài
            state["current_step"] = "end"
            return state

        except Exception as e:
            self.logger.error(f"Error in finalize node: {e}")
            state["error"] = str(e)
            state["current_step"] = "end"
            return state
        
        finally:
            # End timing and log
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[{session_id}] Completed {node_name} execution: {duration:.2f}s")


    def _should_continue(self, state: AgentStateDict) -> str:
        """Determine if the workflow should continue"""
        # if state["error"]:
        #     return "end"

        current_step = state["current_step"]

        if current_step == "end":
            return "end"
        elif current_step == "tools":
            return "tools"
        elif current_step == "llm":
            return "llm"
        elif current_step == "final":
            return "final"

        # Default: end the workflow
        return "end"

    async def stream(self, message: str, session_id: Optional[str] = None, chat_history: List[BaseMessage] = []):
        """Process a message and stream each state during execution"""
        # Start timing for entire stream process
        total_start_time = time.time()
        session_id = session_id or str(uuid.uuid4())
        
        # Store chat_history for use in nodes (e.g. history summarization)
        self.chat_history = chat_history
        
        logger.info(f"[{session_id}] Chat history stored: {len(self.chat_history)} messages")
        
        logger.info(f"[{session_id}] Starting stream process for message: {message[:100]}...")
        current_task = asyncio.current_task()
        if current_task:
            self._stream_tasks[session_id] = current_task
        
        try:
            try:
                # Log query enhancement start
                enhancement_start_time = time.time()
                logger.info(f"[{session_id}] Starting query enhancement")
                
                # Enhancing query
                # enhanced_query = self.reflection_engine.enhance_query(
                #     message,
                #     chat_history,
                #     config.DEFAULT_N_LAST_INTERACTIONS,
                #     config.DEFAULT_MAX_CONTENT_REWRITE_LENGTH
                # )
                enhanced_query_text = message
                # enhanced_query_text = enhanced_query.get("enhanced_query", "")
                
                self.llm_calls[session_id] = {
                    "enhanced_query": {
                        "system_prompt": '',
                        "message": message,
                        # "qa_prompt": enhanced_query.get("prompt", ""),
                        "qa_prompt": '',
                        "response": enhanced_query_text,
                    }
                }
                
                # Log query enhancement end
                enhancement_end_time = time.time()
                enhancement_duration = enhancement_end_time - enhancement_start_time
                # logger.info(f"[{session_id}] Query enhancement completed: {enhancement_duration:.2f}s")
                
            except Exception as e:
                logger.error(f"Error in enhancing query: {str(e)}")

            # Run the graph with state tracking
            config_session: RunnableConfig = {"configurable": {"thread_id": session_id}}
            
            messages = chat_history if chat_history else []
            messages.append(HumanMessage(content=(enhanced_query_text if enhanced_query_text else message)))
            
            # Create initial state
            initial_state: AgentStateDict = {
                "messages": messages,
                "current_step": "llm",
                "error": None,
                "tool_calls": [],
                "tool_results": [],
                "session_id": session_id,
                "timestamp": datetime.now(),
                "metadata": {},
                "config": config_session,
                "iteration_count": 0,
            }

            # Yield initial state
            yield initial_state

            if self.graph is None:
                yield {"type": "error", "message": "Graph not initialized"}
                return

            # Log graph execution start
            graph_execution_start = time.time()
            logger.info(f"[{session_id}] Starting graph execution")

            agen = self.graph.astream(initial_state, config_session)

            try:
                async for event in agen:
                    for _, v in event.items():
                        # logger.info(f"[{session_id}] Yielding state update: {v}") # fix here
                        yield v
            except asyncio.CancelledError:
                logger.info(f"[{session_id}] Stream cancelled by terminate()")

            graph_execution_end = time.time()
            graph_execution_duration = graph_execution_end - graph_execution_start
            logger.info(f"[{session_id}] Graph execution completed: {graph_execution_duration:.2f}s")

        except Exception as e:
            self.logger.error(f"Error in streaming: {e}")
            yield {"type": "error", "message": str(e)}
        
        finally:
            self._stream_tasks.pop(session_id, None)
            # Log total processing time
            total_end_time = time.time()
            total_duration = total_end_time - total_start_time
            logger.info(f"[{session_id}] Total stream process completed: {total_duration:.2f}s")

    async def terminate(self, session_id: str, reason: str = "Cancelled by client"):
        config: RunnableConfig = {"configurable": {"thread_id": session_id}}

        task = self._stream_tasks.get(session_id)
        if task and not task.done():
            try:
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning(f"[{session_id}] Stream task did not finish within timeout after cancel()")
            except Exception as e:
                logger.warning(f"[{session_id}] Failed to cancel stream task: {e!r}")
            finally:
                self._stream_tasks.pop(session_id, None)

        try:
            snap = self.graph.get_state(config)
            values = dict(getattr(snap, "values", {}) or {})
            now = datetime.now().isoformat()
            note = f"[TERMINATED {now}] {reason}"

            values["current_step"] = "end"
            prev_err = values.get("error")
            values["error"] = f"{prev_err} | {note}" if prev_err else note

            msgs = list(values.get("messages", []))
            msgs.append(SystemMessage(content=note))
            values["messages"] = msgs

            self.graph.update_state(config, values)
            logger.info(f"[{session_id}] State updated to end")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to update state to end: {e!r}")
            
            
# # Test
# if __name__ == "__main__":
#     def _extract_tool_call(response: str) -> Optional[Dict[str, Any]]:
#         # Lấy nội dung trong @@CALL_TOOL@@ ... @@END@@
#         match = re.search(r'@@CALL_TOOL@@\s*(.*?)@@END@@', response, re.DOTALL)
#         if not match:
#             return None

#         body = match.group(1)

#         name_match = re.search(r'tool_name:\s*(\S+)', body)
#         args_match = re.search(r'arguments:\s*(\{.*\})', body, re.DOTALL)

#         if not name_match or not args_match:
#             return None

#         try:
#             arguments = json.loads(args_match.group(1))
#         except json.JSONDecodeError:
#             return None

#         return {
#             "tool_name": name_match.group(1).strip(),
#             "arguments": arguments
#         }
#     response = """@@CALL_TOOL@@
# tool_name: web_search_internet
# arguments: {"query":"giá vàng hôm nay","max_urls":2}
# @@END@@"""
#     print(_extract_tool_call(response))

