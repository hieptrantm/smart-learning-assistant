import logging
import os
from typing import Any, List, Optional, Callable
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import BaseTool

load_dotenv()
class BaseLangGraphAgent:
    """
    Base class for LangGraph-based agents.
    Provides common workflow setup, graph management, and invoke/stream logic.
    Subclasses should define state dict, node logic, and edge logic.
    """
    def __init__(
        self,
        state_dict_type: Any,
        tools: Optional[List[BaseTool]] = None,
        callback_text_generate: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        self.logger = logging.getLogger(f"agent init")
        self.state_dict_type = state_dict_type
        self.tools = tools or []
        self.callback_text_generate = callback_text_generate
        self.args = args or []
        self.kwargs = kwargs or {}
        self.workflow = None
        self.graph = None
        self.store = None
        self.checkpointer = None
        self._initialized = False

    @classmethod
    async def create(
        cls,
        state_dict_type: Any,
        tools: Optional[List[BaseTool]] = None,
        callback_text_generate: Optional[Callable] = None,
        store: Optional[AsyncPostgresStore] = None,
        checkpointer: Optional[AsyncPostgresSaver | InMemorySaver] = None,
        *args,
        **kwargs,
    ):
        """Factory method to create and initialize the agent."""
        instance = cls(state_dict_type, tools, callback_text_generate, *args, **kwargs)
        await instance._async_init(store, checkpointer)
        return instance
    
    async def _async_init(self, store: Optional[AsyncPostgresStore] = None, checkpointer: Optional[AsyncPostgresSaver | InMemorySaver] = None):
        if self._initialized:
            return
        self.store = store
        self.checkpointer = checkpointer or InMemorySaver()
        self._setup_graph()
        self._initialized = True

    def _setup_graph(self):
        """
        Setup the LangGraph workflow. Subclasses should override to add nodes and edges.
        """
        self.workflow = StateGraph(self.state_dict_type)
        # Subclass should add nodes and edges here
        # self.workflow.add_node(...)
        # self.workflow.add_conditional_edges(...)
        # self.workflow.set_entry_point(...)
        self.graph = self.workflow.compile(checkpointer=self.checkpointer, store=self.store)

    def _ensure_initialized(self):
        """check if the agent is initialized"""
        if not self._initialized:
            raise RuntimeError("Agent must be initialized with create() before use.")

    async def invoke(self, message: str, session_id: Optional[str] = None) -> str:
        self._ensure_initialized()
        raise NotImplementedError("Subclasses must implement invoke method.")

    async def continue_invoke(self, resume: Any, session_id: str):
        self._ensure_initialized()
        raise NotImplementedError("Subclasses must implement continue_invoke method.")

    async def stream(self, message: str, session_id: Optional[str] = None):
        self._ensure_initialized()
        raise NotImplementedError("Subclasses must implement stream method.")

    async def continue_stream(self, resume: Any, session_id: str):
        self._ensure_initialized()
        raise NotImplementedError("Subclasses must implement continue_stream method.") 