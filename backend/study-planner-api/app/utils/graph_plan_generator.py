import logging
import os
from datetime import date, timedelta

from neo4j import AsyncGraphDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from app.models.study_subject import StudySubject
from app.utils.graph_scheduler import (
    GraphScheduler,
    graph_node_from_neo4j,
    graph_relationship_from_neo4j,
)

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun",
}


class GraphPlanGenerator:
    def __init__(
        self,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_password: str = NEO4J_PASSWORD,
        output_dir: str = None,
        llm_client=None,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "output")
        self.llm_client = llm_client
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate(
        self,
        db_url: str,
        subject_id: int,
        subject_name: str,
        end_date_str: str,
        checkpoint_node_id: str = None,
    ) -> list[dict]:
        start_date = date.today()
        end_date = date.fromisoformat(end_date_str) if isinstance(end_date_str, str) else end_date_str

        sessions = self._build_session_slots(db_url, subject_id, start_date, end_date)
        if not sessions:
            logger.warning("[GraphPlanGenerator] No sessions from free slots")
            return []

        scheduler = await self._build_graph_scheduler(subject_name)
        num_content = len(scheduler._nodes)
        if num_content == 0:
            logger.warning("[GraphPlanGenerator] No graph data for %s", subject_name)
            return []

        if len(sessions) > num_content:
            step = len(sessions) / num_content
            sessions = [sessions[int(index * step)] for index in range(num_content)]

        weights = [session["hours"] for session in sessions]
        results = await scheduler.schedule(weights, checkpoint_node_id)
        return self._to_calendar_events(sessions, results, subject_name)

    def _build_session_slots(self, db_url, subject_id, start_date, end_date):
        engine = create_engine(db_url, pool_pre_ping=True)
        slots_by_day = {}

        with DBSession(engine) as db:
            subj = db.query(StudySubject).filter_by(id=subject_id).first()
            if not subj:
                return []
            for slot in subj.free_slots:
                day = slot.day_of_week
                if day not in slots_by_day:
                    slots_by_day[day] = []
                slots_by_day[day].append(slot.time_slot)

        if not slots_by_day:
            return []

        sessions = []
        current = start_date + timedelta(days=1)
        while current <= end_date:
            day_key = WEEKDAY_MAP[current.weekday()]
            if day_key in slots_by_day:
                parsed = []
                for time_slot in sorted(slots_by_day[day_key]):
                    start_time, end_time, hours = self._parse_time_slot(time_slot)
                    if hours > 0:
                        parsed.append((start_time, end_time, hours))

                merged = []
                for start_time, end_time, hours in parsed:
                    if merged and merged[-1]["end_time"] == start_time:
                        merged[-1]["end_time"] = end_time
                        merged[-1]["hours"] += hours
                    else:
                        merged.append({"start_time": start_time, "end_time": end_time, "hours": hours})

                for slot in merged:
                    sessions.append({
                        "date": current.isoformat(),
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "hours": slot["hours"],
                    })
            current += timedelta(days=1)
        return sessions

    @staticmethod
    def _parse_time_slot(time_slot):
        if "-" not in time_slot:
            try:
                parts = time_slot.strip().split(":")
                s_min = int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
                e_min = s_min + 60
                start_fmt = f"{s_min // 60:02d}:{s_min % 60:02d}"
                end_fmt = f"{e_min // 60:02d}:{e_min % 60:02d}"
                return start_fmt, end_fmt, 1.0
            except (ValueError, IndexError):
                return time_slot, time_slot, 1.0

        start_str, end_str = time_slot.split("-", 1)
        start_str, end_str = start_str.strip(), end_str.strip()
        try:
            s_parts = start_str.split(":")
            e_parts = end_str.split(":")
            s_min = int(s_parts[0]) * 60 + (int(s_parts[1]) if len(s_parts) > 1 else 0)
            e_min = int(e_parts[0]) * 60 + (int(e_parts[1]) if len(e_parts) > 1 else 0)
            hours = max((e_min - s_min) / 60, 0.5)
            start_fmt = f"{s_min // 60:02d}:{s_min % 60:02d}"
            end_fmt = f"{e_min // 60:02d}:{e_min % 60:02d}"
            return start_fmt, end_fmt, hours
        except (ValueError, IndexError):
            return start_str, end_str, 1.0

    async def _build_graph_scheduler(self, subject_name: str) -> GraphScheduler:
        nodes, relationships = await self._fetch_graph_snapshot(subject_name)
        logger.info(
            "[GraphPlanGenerator] Fetched raw graph for %s: %s nodes, %s relationships",
            subject_name,
            len(nodes),
            len(relationships),
        )
        return GraphScheduler(nodes, relationships, llm_client=self.llm_client)

    async def _fetch_graph_snapshot(self, subject_name: str):
        driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        nodes = {}
        relationships = {}
        try:
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (n:Entity {subject_id: $sid})
                    OPTIONAL MATCH (n)-[r]->(m:Entity {subject_id: $sid})
                    RETURN n, r, m
                    """,
                    sid=subject_name,
                )
                async for record in result:
                    node = record["n"]
                    nodes[node.id] = graph_node_from_neo4j(node)

                    rel = record["r"]
                    target = record["m"]
                    if rel is None or target is None:
                        continue

                    nodes[target.id] = graph_node_from_neo4j(target)
                    relationships[rel.id] = graph_relationship_from_neo4j(rel)
        finally:
            await driver.close()

        return list(nodes.values()), list(relationships.values())

    @staticmethod
    def _to_calendar_events(sessions, results, subject_name):
        events = []
        for session_info, result in zip(sessions, results):
            if not result.nodes:
                continue

            d = session_info["date"]
            st = session_info["start_time"][:5]
            et = session_info["end_time"][:5]

            if result.title:
                summary = result.title
            else:
                summary = f"{subject_name} - {', '.join(node.name for node in result.nodes)}"

            if result.description:
                description = result.description
            else:
                desc_parts = []
                for node in result.nodes:
                    if node.description:
                        desc_parts.append(f"- {node.name}: {node.description[:300]}")
                    for tag in node.tags:
                        desc_parts.append(f"  [{tag.get('rel_type', '')}] -> {tag.get('target_name', '')}")
                description = "\n".join(desc_parts) if desc_parts else f"Nội dung học {subject_name}"

            events.append({
                "summary": summary[:250],
                "location": "Online",
                "description": description,
                "aggregated_content": result.aggregate_text if result.aggregate_text else description,
                "checkpoint_node_id": result.checkpoint_node_id if result.checkpoint_node_id else "graph_root",
                "start": {
                    "dateTime": f"{d}T{st}:00+07:00",
                    "timeZone": "Asia/Ho_Chi_Minh",
                },
                "end": {
                    "dateTime": f"{d}T{et}:00+07:00",
                    "timeZone": "Asia/Ho_Chi_Minh",
                },
            })
        return events
