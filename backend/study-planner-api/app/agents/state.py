"""
state.py -- PlannerStateDict for the LangGraph study planner agent.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict


class PlannerStateDict(TypedDict, total=False):
    # Identity
    subject_id: int
    user_id: int
    db_url: str
    checkpoint_chunk_id: Optional[str]
    checkpoint_node_id: Optional[str]

    # Subject data from DB
    subjects: List[Dict[str, Any]]
    completed_subjects: List[Dict[str, Any]]
    pending_plan_subjects: List[Dict[str, Any]]
    missed_sessions: List[Dict[str, Any]]

    # Planner output (list of Google Calendar event dicts)
    plan_result: Optional[List[Dict[str, Any]]]
    current_subject: Optional[Dict[str, Any]]

    # Observation / recommendation
    recommend_context: Optional[str]

    # Tool interaction
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    # Google OAuth tokens (passed per request)
    google_access_token: Optional[str]
    google_refresh_token: Optional[str]

    # Routing
    current_step: str       # check_status | observation | planner | tools | end
    previous_step: str

    # Counters
    iteration_count: int
    email_retry_count: int

    # Error tracking
    error: Optional[str]
    timestamp: datetime
