"""
planner_orchestrator.py -- Background task that:
  1. Sends PDF to data-ingestor for indexing
  2. Polls ingest status until done
  3. Runs the LangGraph planner agent (check_status -> observation -> planner -> tools -> end)
"""

import asyncio
import traceback
from datetime import datetime
from typing import Optional

from app.config import DATABASE_URL
from app.database import SessionLocal
from app.models.study_subject import StudySubject
from app.models.study_session import StudySession

import logging
logger = logging.getLogger(__name__)

# Singleton agent reference, set from main.py lifespan
_planner_agent = None


def set_planner_agent(agent):
    """Set the singleton planner agent instance."""
    global _planner_agent
    _planner_agent = agent

async def run_full_pipeline(
    subject_id: int,
    google_access_token: Optional[str] = None,
    google_refresh_token: Optional[str] = None,
):
    """
    Full background pipeline:
      PDF -> data-ingestor -> wait ingest -> LangGraph agent
    """
    db = SessionLocal()
    try:
        subject = db.query(StudySubject).filter_by(id=subject_id).first()
        if not subject:
            logger.error(f"[orchestrator] Subject {subject_id} not found")
            return
            
        # check if already ingested (should be the case for this code path, but just in case) 
        # if subject.ingest_status == "completed":
        #     logger.info(f"[pipeline] Subject {subject_id} already ingested (status=completed), continue planning.")
        # else: 
        #     return 

        # Find existing sessions, determine checkpoint, and clean up non-passed sessions
        checkpoint_node_id = None
        sessions = (
            db.query(StudySession)
            .filter_by(subject_id=subject_id)
            .order_by(StudySession.session_date, StudySession.start_time)
            .all()
        )

        if sessions:
            first_non_passed_idx = None
            for i, sess in enumerate(sessions):
                if sess.learning_status != "passed":
                    first_non_passed_idx = i
                    break

            if first_non_passed_idx is not None:
                # Checkpoint from the last passed session (the one before the first non-passed)
                if first_non_passed_idx > 0:
                    checkpoint_node_id = sessions[first_non_passed_idx - 1].checkpoint_node_id
                # Delete the first non-passed session and all subsequent sessions
                session_ids_to_delete = [s.id for s in sessions[first_non_passed_idx:]]
                if session_ids_to_delete:
                    db.query(StudySession).filter(
                        StudySession.id.in_(session_ids_to_delete)
                    ).delete(synchronize_session="fetch")
                    db.commit()
                    logger.info(
                        f"[orchestrator] Deleted {len(session_ids_to_delete)} non-passed sessions "
                        f"for subject {subject_id}, checkpoint_node_id={checkpoint_node_id}"
                    )

        # Run LangGraph agent
        try:
            subject.plan_status = "generating"
            db.commit()

            initial_state = {
                "subject_id": subject.id,
                "user_id": subject.user_id,
                "db_url": DATABASE_URL,
                "checkpoint_node_id": checkpoint_node_id,
                "google_access_token": google_access_token,
                "google_refresh_token": google_refresh_token,
                "subjects": [],
                "completed_subjects": [],
                "pending_plan_subjects": [],
                "missed_sessions": [],
                "plan_result": None,
                "current_subject": None,
                "recommend_context": None,
                "tool_calls": [],
                "tool_results": [],
                "current_step": "check_status",
                "previous_step": "",
                "iteration_count": 0,
                "email_retry_count": 0,
                "error": None,
                "timestamp": datetime.now(),
            }

            final_state = await _planner_agent.ainvoke(initial_state)

            # Update subject status based on result
            if final_state.get("error"):
                subject.plan_status = "failed"
                logger.error(f"[orchestrator] Agent error: {final_state['error']}")
            elif final_state.get("plan_result"):
                subject.plan_status = "completed"
                subject.ingest_status = "completed"
            elif final_state.get("current_subject", {}).get("ingest_status") == "processing":
                subject.plan_status = "pending"
                logger.info(
                    f"[orchestrator] Subject {subject_id} ingest still processing, skip plan generation"
                )
            else:
                subject.plan_status = "failed"

            db.commit()

        except Exception as e:
            subject.plan_status = "failed"
            db.commit()
            logger.error(f"[orchestrator] Agent execution failed: {e}")
            traceback.print_exc()
    finally:
        db.close()
