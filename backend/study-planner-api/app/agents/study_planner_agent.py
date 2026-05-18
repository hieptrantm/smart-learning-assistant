from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.agents.state import PlannerStateDict
from app.config import (
    OBSERVATION_SCORE_PROMPT,
    EMAIL_SUBJECT_TEMPLATE,
    EMAIL_BODY_TEMPLATE,
    EMAIL_SESSION_ROW,
    EMAIL_MAX_RETRIES,
    SCHEDULE_TOOL_BATCH_SIZE,
)
from app.models.study_subject import StudySubject
from app.utils.plan_generator import PlanGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StudyPlannerAgent:
    """LangGraph-based study planner with check_status/observation/planner/tools nodes."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, llm_client=None, tools: Optional[List] = None, qdrant_service=None):
        if not self._initialized:
            self.llm = llm_client
            self.tools = tools or []
            self.plan_generator = PlanGenerator(llm_client=llm_client)
            self.graph = self._build_graph()
            self.qdrant_service = qdrant_service
            self.__class__._initialized = True
            logger.info("Initialized StudyPlannerAgent")

    def set_tools(self, tools: List):
        """Update MCP tools (called after lifespan init)."""
        self.tools = tools

    # ── Graph builder ──────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(PlannerStateDict)

        graph.add_node("check_status", self._check_status_node)
        graph.add_node("observation", self._observation_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("tools", self._tools_node)

        graph.set_entry_point("check_status")

        graph.add_conditional_edges(
            "check_status", self._route,
            {"observation": "observation", "planner": "planner", "end": END},
        )
        graph.add_conditional_edges(
            "observation", self._route,
            {"planner": "planner", "tools": "tools", "end": END},
        )
        graph.add_edge("planner", "observation")
        graph.add_conditional_edges(
            "tools", self._route,
            {"observation": "observation", "end": END},
        )

        return graph.compile()

    @staticmethod
    def _route(state: PlannerStateDict) -> str:
        return state.get("current_step", "end")

    # ── Node: check_status ─────────────────────────────────────

    async def _check_status_node(self, state: PlannerStateDict) -> dict:
        """Load one subject by id and route based on its ingest status."""
        logger.info(
            f"[check_status] subject_id={state.get('subject_id')} user_id={state.get('user_id')}"
        )

        engine = create_engine(state["db_url"], pool_pre_ping=True)
        subject_id = state.get("subject_id")

        if subject_id is None:
            logger.error("[check_status] Missing subject_id in planner state")
            return {
                "current_step": "end",
                "previous_step": "check_status",
                "error": "Missing subject_id",
            }

        with DBSession(engine) as db:
            subject = db.query(StudySubject).filter_by(id=subject_id).first()

            if not subject:
                logger.info(f"[check_status] Subject {subject_id} not found")
                return {
                    "current_step": "end",
                    "previous_step": "check_status",
                    "error": f"Subject {subject_id} not found",
                }

            subject_dict = {
                "id": subject.id,
                "name": subject.name,
                "ingest_status": subject.ingest_status,
                "plan_status": subject.plan_status,
                "target_grade": float(subject.target_grade or 7),
                "end_date": subject.end_date.isoformat() if subject.end_date else "",
                "checkpoint_chunk_id": state.get("checkpoint_chunk_id") or state.get("checkpoint_node_id"),
                "checkpoint_node_id": state.get("checkpoint_node_id"),
            }

            if subject.ingest_status == "completed":
                logger.info(f"[check_status] Subject {subject_id} ingest completed -> planner")
                return {
                    "subjects": [subject_dict],
                    "completed_subjects": [subject_dict],
                    "pending_plan_subjects": [subject_dict],
                    "current_subject": subject_dict,
                    "current_step": "planner",
                    "previous_step": "check_status",
                }

            if subject.ingest_status == "processing":
                logger.info(f"[check_status] Subject {subject_id} ingest still processing -> end")
                return {
                    "subjects": [subject_dict],
                    "current_subject": subject_dict,
                    "current_step": "end",
                    "previous_step": "check_status",
                }

            logger.info(
                f"[check_status] Subject {subject_id} ingest_status={subject.ingest_status} -> end"
            )
            return {
                "subjects": [subject_dict],
                "current_subject": subject_dict,
                "current_step": "end",
                "previous_step": "check_status",
            }

    # ── Node: observation ──────────────────────────────────────

    async def _observation_node(self, state: PlannerStateDict) -> dict:
        """Route based on previous step results. LLM-driven for score analysis."""
        prev = state.get("previous_step", "")
        logger.info(f"[observation] previous_step={prev}")

        # Case 1: After check_status, all sessions completed -> evaluate scores
        if prev == "check_status":
            return await self._observe_scores(state)

        # Case 2: After planner, plan ready -> call build_schedule tool
        if prev == "planner" and state.get("plan_result"):
            return self._observe_schedule_plan(state)

        # Case 3: After tools, check tool result
        if prev == "tools":
            return self._observe_tool_result(state)

        # Default: end
        return {"current_step": "end", "previous_step": "observation"}

    async def _observe_scores(self, state: PlannerStateDict) -> dict:
        """Evaluate student scores vs target, recommend changes if needed."""
        from app.models.study_session import StudySession

        completed = state.get("completed_subjects", [])
        if not completed:
            return {"current_step": "end", "previous_step": "observation"}

        subject = completed[0]
        engine = create_engine(state["db_url"], pool_pre_ping=True)

        with DBSession(engine) as db:
            sessions = db.query(StudySession).filter_by(
                subject_id=subject["id"]
            ).filter(StudySession.status == "completed").all()

            if not sessions:
                return {"current_step": "end", "previous_step": "observation"}

            # Calculate average score (score field may not exist, skip if so)
            scores = []
            session_info = []
            for s in sessions:
                session_info.append(f"{s.title} ({s.session_date})")
                if hasattr(s, "score") and s.score is not None:
                    scores.append(float(s.score))

            avg_score = sum(scores) / len(scores) if scores else 0
            target = subject.get("target_grade", 7)

            # Use LLM to evaluate
            prompt = OBSERVATION_SCORE_PROMPT.format(
                avg_score=avg_score,
                target_grade=target,
                completed_sessions="; ".join(session_info[:10]),
            )

            try:
                response = await self.llm.ainvoke(prompt)
                recommend = response.content.strip()
            except Exception as e:
                logger.error(f"[observation] LLM score eval error: {e}")
                recommend = ""

            if recommend and avg_score < target:
                return {
                    "recommend_context": recommend,
                    "current_subject": subject,
                    "current_step": "planner",
                    "previous_step": "observation",
                }
        return {"current_step": "end", "previous_step": "observation"}

    def _observe_schedule_plan(self, state: PlannerStateDict) -> dict:
        """Plan is ready, format build_schedule tool calls."""
        plan_result = state.get("plan_result", [])
        if not plan_result:
            return {"current_step": "end", "previous_step": "observation"}
        
        if isinstance(plan_result, str):
            plan_result = self._parse_plan_json(plan_result)
        filtered_plan_result = []
        for plan in plan_result:
            filtered_plan_result.append({
                "summary": plan.get("summary", ""),
                "location": plan.get("location", ""),
                "description": plan.get("description", ""),
                "start": plan.get("start", {}),
                "end": plan.get("end", {}),
            })
        
        logger.info(f"[observation] Plan ready with {len(filtered_plan_result)} events, preparing tool calls")
        logger.info(f"Google access token: {state.get('google_access_token')}")
        logger.info(f"Google refresh token: {state.get('google_refresh_token')}")


        tool_calls = list(state.get("tool_calls", []))
        for event in filtered_plan_result:
            tool_calls.append({
                "tool_name": "build_one_schedule",
                "parameters": {
                    "event_json": json.dumps(event, ensure_ascii=False),
                    "google_access_token": state.get("google_access_token") or "",
                    "google_refresh_token": state.get("google_refresh_token") or "",
                },
                "status": "pending",
            })

        return {
            "tool_calls": tool_calls,
            "current_step": "tools",
            "previous_step": "observation",
        }

    def _observe_tool_result(self, state: PlannerStateDict) -> dict:
        """Check last tool result and decide next action."""
        tool_results = state.get("tool_results", [])
        tool_calls = state.get("tool_calls", [])

        if not tool_results:
            return {"current_step": "end", "previous_step": "observation"}

        last_result = tool_results[-1]
        last_tool = last_result.get("tool_name", "")
        success = last_result.get("success", False)

        # If build_one_schedule done, check if more pending schedule calls
        if last_tool == "build_one_schedule":
            pending = [t for t in tool_calls if t.get("status") == "pending"]
            if pending:
                # More events to create
                return {"current_step": "tools", "previous_step": "observation"}

            # All events created -> send email
            if success or any(r.get("success") for r in tool_results if r.get("tool_name") == "build_schedule"):
                subject = state.get("current_subject", {})
                plan_result = state.get("plan_result", [])

                session_rows = ""
                for idx, ev in enumerate(plan_result):
                    start_dt = ev.get("start", {}).get("dateTime", "")
                    end_dt = ev.get("end", {}).get("dateTime", "")
                    date_str, time_start = self._format_dt_vn(start_dt)
                    _, time_end = self._format_dt_vn(end_dt)
                    row_bg = "#f8fafc" if idx % 2 == 0 else "#ffffff"
                    session_rows += EMAIL_SESSION_ROW.format(
                        date=date_str,
                        time_start=time_start,
                        time_end=time_end,
                        summary=ev.get("summary", ""),
                        description=ev.get("description", ""),
                        row_bg=row_bg,
                        idx=idx + 1,
                    )

                user_email, username = self._get_user_info(state)
                total_sessions = len(plan_result)

                html_content = EMAIL_BODY_TEMPLATE.format(
                    subject_name=subject.get("name", ""),
                    target_grade=subject.get("target_grade", 7),
                    total_sessions=total_sessions,
                    username=username,
                    session_rows=session_rows,
                )
                email_subject = EMAIL_SUBJECT_TEMPLATE.format(
                    subject_name=subject.get("name", ""),
                )

                new_calls = list(tool_calls)
                new_calls.append({
                    "tool_name": "send_email",
                    "parameters": {
                        "to_email": user_email,
                        "subject": email_subject,
                        "html_content": html_content,
                    },
                    "status": "pending",
                })

                return {
                    "tool_calls": new_calls,
                    "current_step": "tools",
                    "previous_step": "observation",
                }

        # If send_email succeeded -> end
        if last_tool == "send_email" and success:
            return {"current_step": "end", "previous_step": "observation"}

        # If send_email failed -> check retry count
        if last_tool == "send_email" and not success:
            retry_count = state.get("email_retry_count", 0)
            if retry_count < EMAIL_MAX_RETRIES:
                # Re-add the same call for retry
                pending_email = [t for t in tool_calls if t.get("tool_name") == "send_email"]
                if pending_email:
                    pending_email[-1]["status"] = "pending"
                return {
                    "tool_calls": tool_calls,
                    "email_retry_count": retry_count + 1,
                    "current_step": "tools",
                    "previous_step": "observation",
                }
            return {"current_step": "end", "previous_step": "observation"}

        # If any tool error -> retry via observation
        if not success:
            return {"current_step": "end", "previous_step": "observation"}

        return {"current_step": "end", "previous_step": "observation"}

    def _get_user_email(self, state: PlannerStateDict) -> str:
        """Fetch user email from DB (legacy, use _get_user_info instead)."""
        email, _ = self._get_user_info(state)
        return email

    def _get_user_info(self, state: PlannerStateDict) -> tuple[str, str]:
        """Fetch (email, username) from DB."""
        engine = create_engine(state["db_url"], pool_pre_ping=True)
        with DBSession(engine) as db:
            row = db.execute(
                __import__("sqlalchemy").text(
                    "SELECT email, username FROM users WHERE id = :uid LIMIT 1"
                ),
                {"uid": state.get("user_id")},
            ).fetchone()
            if row:
                return row[0] or "", row[1] or "bạn"
            return "", "bạn"

    @staticmethod
    def _format_dt_vn(iso_str: str) -> tuple[str, str]:
        """Parse ISO datetime string and return (date_vn, time_str).
        e.g. '2025-01-15T08:00:00+07:00' -> ('Thứ 4, 15/01/2025', '08:00')
        """
        try:
            from datetime import datetime, timezone, timedelta
            dt = datetime.fromisoformat(iso_str)
            # Ensure UTC+7
            vn_tz = timezone(timedelta(hours=7))
            dt = dt.astimezone(vn_tz)
            day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
            day_vn = day_names[dt.weekday()]
            date_str = f"{day_vn}, {dt.day:02d}/{dt.month:02d}/{dt.year}"
            time_str = dt.strftime("%H:%M")
            return date_str, time_str
        except Exception:
            # fallback: return raw string split
            parts = iso_str.split("T")
            return parts[0] if parts else iso_str, parts[1][:5] if len(parts) > 1 else ""

    # ── Node: planner ──────────────────────────────────────────

    async def _planner_node(self, state: PlannerStateDict) -> dict:
        """Generate study plan from tree-based graph nodes."""
        subject = state.get("current_subject") or {}
        if not subject:
            pending = state.get("pending_plan_subjects", [])
            subject = pending[0] if pending else {}
        if not subject:
            return {"current_step": "end", "previous_step": "planner", "error": "No subject to plan"}

        logger.info(f"[planner] Generating plan for subject: {subject.get('name')}")

        try:
            plan = await self.plan_generator.generate(
                db_url=state["db_url"],
                subject_id=subject["id"],
                subject_name=subject.get("name", ""),
                end_date_str=subject.get("end_date", ""),
                checkpoint_chunk_id=subject.get("checkpoint_chunk_id", None),
                checkpoint_node_id=subject.get("checkpoint_node_id", None),
            )
            logger.info(f"[planner] Plan generation completed with {len(plan)} events")
        except Exception as e:
            logger.error(f"[planner] Generation error: {e}")
            return {
                "current_step": "end",
                "previous_step": "planner",
                "error": f"Plan generation failed: {e}",
            }

        if not plan:
            return {
                "current_step": "end",
                "previous_step": "planner",
                "error": "No plan generated (empty tree or no free slots)",
            }

        logger.info(f"[planner] Plan generated: {len(plan)} events")
        await self._save_plan_to_db(state, subject, plan)

        return {
            "plan_result": plan,
            "current_subject": subject,
            "current_step": "observation",
            "previous_step": "planner",
        }

    def _build_free_desc(self, state: PlannerStateDict) -> str:
        """Build free time description from DB slots."""
        from app.models.study_subject import StudySubject

        subject = state.get("current_subject", {})
        if not subject:
            return "  Không có thời gian rảnh cụ thể.\n"

        day_names = {
            "mon": "Thứ 2", "tue": "Thứ 3", "wed": "Thứ 4",
            "thu": "Thứ 5", "fri": "Thứ 6", "sat": "Thứ 7", "sun": "Chủ nhật",
        }

        engine = create_engine(state["db_url"], pool_pre_ping=True)
        free_time: Dict[str, list] = {}

        with DBSession(engine) as db:
            subj = db.query(StudySubject).filter_by(id=subject["id"]).first()
            if subj:
                for slot in subj.free_slots:
                    day = slot.day_of_week
                    if day not in free_time:
                        free_time[day] = []
                    free_time[day].append(slot.time_slot)

        if not free_time:
            return "  Không có thời gian rảnh cụ thể.\n"

        desc = ""
        for day, slots in free_time.items():
            desc += f"  - {day_names.get(day, day)}: {', '.join(sorted(slots))}\n"
        return desc


    def _parse_plan_json(self, text: str) -> Optional[List[Dict]]:
        """Extract JSON array of calendar events from LLM response."""
        # Strip markdown fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        # Try to find JSON array
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                plan = json.loads(match.group())
                logger.info(f"Extracted plan JSON with {len(plan)} events:\n {plan}")
                if isinstance(plan, list) and len(plan) > 0:
                    return plan
            except json.JSONDecodeError:
                pass

        # Try to find JSON object with sessions array
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                obj = json.loads(match.group())
                sessions = obj.get("sessions", [])
                if sessions:
                    logger.info(f"Extracted sessions JSON with {len(sessions)} events:\n {sessions}")
                    # Convert session format to calendar event format
                    return self._convert_sessions_to_events(sessions, obj.get("subject", ""))
            except json.JSONDecodeError:
                pass

        return None

    def _convert_sessions_to_events(self, sessions: List[Dict], subject_name: str) -> List[Dict]:
        """Convert old-format sessions to Google Calendar event dicts."""
        events = []
        for s in sessions:
            date_str = s.get("session_date", "")
            start_time = s.get("start_time", "08:00")
            end_time = s.get("end_time", "09:00")
            events.append({
                "summary": s.get("title", f"Học {subject_name}"),
                "location": "Online",
                "description": s.get("content", ""),
                "start": {
                    "dateTime": f"{date_str}T{start_time}:00+07:00",
                    "timeZone": "Asia/Ho_Chi_Minh",
                },
                "end": {
                    "dateTime": f"{date_str}T{end_time}:00+07:00",
                    "timeZone": "Asia/Ho_Chi_Minh",
                },
            })
        return events

    async def _save_plan_to_db(self, state: PlannerStateDict, subject: Dict, plan: List[Dict]):
        """Persist generated plan to study_plans and study_sessions tables."""
        from app.models.study_plan import StudyPlan
        from app.models.study_session import StudySession
        from app.models.study_subject import StudySubject

        engine = create_engine(state["db_url"], pool_pre_ping=True)
        try:
            with DBSession(engine) as db:
                plan_record = StudyPlan(
                    subject_id=subject["id"],
                    plan_json=plan,
                )
                db.add(plan_record)
                db.flush()

                for ev in plan:
                    start_dt = ev.get("start", {}).get("dateTime", "")
                    end_dt = ev.get("end", {}).get("dateTime", "")

                    # Extract date and time from ISO format
                    session_date = start_dt[:10] if len(start_dt) >= 10 else ""
                    start_time = start_dt[11:16] if len(start_dt) >= 16 else "08:00"
                    end_time = end_dt[11:16] if len(end_dt) >= 16 else "09:00"

                    session = StudySession(
                        plan_id=plan_record.id,
                        subject_id=subject["id"],
                        checkpoint_node_id=ev.get("checkpoint_chunk_id") or ev.get("checkpoint_node_id", None),
                        session_date=date.fromisoformat(session_date) if session_date else None,
                        start_time=start_time,
                        end_time=end_time,
                        title=ev.get("summary", ""),
                        content=ev.get("aggregated_content", ""),
                    )
                    db.add(session)

                subj = db.query(StudySubject).filter_by(id=subject["id"]).first()
                if subj:
                    subj.plan_status = "completed"

                db.commit()
                logger.info(f"[planner] Plan saved for subject_id={subject['id']}")

        except Exception as e:
            logger.error(f"[planner] DB save error: {e}")

    # ── Node: tools ────────────────────────────────────────────

    async def _tools_node(self, state: PlannerStateDict) -> dict:
        """Execute pending MCP tool calls (build_schedule or send_email)."""
        tool_calls = list(state.get("tool_calls", []))
        tool_results = list(state.get("tool_results", []))

        pending_calls = [
            (index, tool_call)
            for index, tool_call in enumerate(tool_calls)
            if tool_call.get("status") == "pending"
        ]

        if not pending_calls:
            return {"current_step": "observation", "previous_step": "tools"}

        first_tool_name = pending_calls[0][1]["tool_name"]
        calls_to_run = (
            pending_calls[:SCHEDULE_TOOL_BATCH_SIZE]
            if first_tool_name == "build_one_schedule"
            else pending_calls[:1]
        )

        logger.info(
            "[tools] Executing %s pending call(s), first tool=%s",
            len(calls_to_run),
            first_tool_name,
        )

        last_tool_name = first_tool_name
        last_result = None
        for pending_idx, pending in calls_to_run:
            tool_name = pending["tool_name"]
            params = pending["parameters"]
            last_tool_name = tool_name
            logger.info(f"[tools] Executing: {tool_name}")

            result = None
            for tool in self.tools:
                if tool.name == tool_name:
                    try:
                        raw = await tool.ainvoke(params)
                        result = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception as e:
                        logger.error(f"[tools] {tool_name} error: {e}")
                        result = {"success": False, "content": "", "error": str(e)}
                    break

            if result is None:
                result = {"success": False, "content": "", "error": f"Tool '{tool_name}' not found"}

            tool_calls[pending_idx]["status"] = "done"
            tool_results.append({
                "tool_name": tool_name,
                "success": result.get("success", False),
                "content": result.get("content", ""),
                "error": result.get("error"),
                "event_id": result.get("event_id", ""),
            })
            last_result = result

        if last_tool_name == "send_email" and last_result and last_result.get("success"):
            return {
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "current_step": "end",
                "previous_step": "tools",
            }

        return {
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "current_step": "observation",
            "previous_step": "tools",
        }

    # ── Public interface ───────────────────────────────────────

    async def ainvoke(self, state: dict) -> dict:
        """Run the planner agent."""
        return await self.graph.ainvoke(state)
