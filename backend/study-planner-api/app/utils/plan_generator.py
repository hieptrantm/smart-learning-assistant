import json
import logging
import os
from datetime import date, timedelta

from neo4j import AsyncGraphDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TREE_SUBJECT_ID_SUFFIX
from app.models.study_subject import StudySubject
from app.utils.scheduler import TreeScheduler

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun",
}


class PlanGenerator:

    def __init__(
        self,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_password: str = NEO4J_PASSWORD,
        tree_suffix: str = TREE_SUBJECT_ID_SUFFIX,
        output_dir: str = None,
        llm_client=None,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.tree_suffix = tree_suffix
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
            logger.warning("[PlanGenerator] No sessions from free slots")
            return []

        tree_subject_id = subject_name + self.tree_suffix
        raw_paths = await self._fetch_tree_paths(tree_subject_id)
        if not raw_paths:
            logger.warning(f"[PlanGenerator] No tree data for {tree_subject_id}")
            return []

        self._save_json(subject_name, raw_paths)

        scheduler = TreeScheduler(raw_paths, llm_client=self.llm_client)
        num_content = len([n for n in scheduler._nodes.values() if n.node_type != "ROOT"])
        if num_content == 0:
            return []

        if len(sessions) > num_content:
            step = len(sessions) / num_content
            sessions = [sessions[int(i * step)] for i in range(num_content)]

        weights = [s["hours"] for s in sessions]
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

                # Merge consecutive slots (end time of previous == start time of next)
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
            # Single time like "07:00" → treat as 1-hour slot ending at start+1h
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

    async def _fetch_tree_paths(self, tree_subject_id):
        driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        raw_paths = []
        try:
            async with driver.session() as session:
                result = await session.run(
                    "MATCH p=(root:TreeRoot {subject_id: $sid})-[*1..]->(n) RETURN p",
                    sid=tree_subject_id,
                )
                async for record in result:
                    raw_paths.append(self._path_to_dict(record["p"]))
        finally:
            await driver.close()
        logger.info(f"[PlanGenerator] Fetched {len(raw_paths)} paths for {tree_subject_id}")
        return raw_paths

    def _path_to_dict(self, path):
        nodes = list(path.nodes)
        rels = list(path.relationships)
        segments = []
        for i, rel in enumerate(rels):
            segments.append({
                "start": self._node_to_dict(nodes[i]),
                "relationship": self._rel_to_dict(rel, nodes[i], nodes[i + 1]),
                "end": self._node_to_dict(nodes[i + 1]),
            })
        return {
            "p": {
                "start": self._node_to_dict(nodes[0]),
                "end": self._node_to_dict(nodes[-1]),
                "segments": segments,
                "length": float(len(rels)),
            }
        }

    @staticmethod
    def _node_to_dict(node):
        return {
            "identity": node.id,
            "labels": list(node.labels),
            "properties": dict(node),
            "elementId": node.element_id,
        }

    @staticmethod
    def _rel_to_dict(rel, start_node, end_node):
        return {
            "identity": rel.id,
            "start": start_node.id,
            "end": end_node.id,
            "type": rel.type,
            "properties": dict(rel),
            "elementId": rel.element_id,
        }

    def _save_json(self, subject_name, raw_paths):
        path = os.path.join(self.output_dir, f"{subject_name}_tree.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_paths, f, ensure_ascii=False, indent=2)
        logger.info(f"[PlanGenerator] Saved tree to {path}")
        return path

    @staticmethod
    def _to_calendar_events(sessions, results, subject_name):
        events = []
        for session_info, result in zip(sessions, results):
            content_nodes = [n for n in result.nodes if n.node_type != "ROOT"]
            if not content_nodes:
                continue

            d = session_info["date"]
            st = session_info["start_time"][:5]
            et = session_info["end_time"][:5]

            # Use LLM-generated title if available, else fallback to node names
            if result.title:
                summary = f"{result.title}"
            else:
                names = [n.name for n in content_nodes]
                summary = f"{subject_name} - {', '.join(names)}"

            # Use LLM-generated description if available, else fallback to node details
            if result.description:
                description = result.description
            else:
                desc_parts = []
                for n in content_nodes:
                    if n.description:
                        desc_parts.append(f"- {n.name}: {n.description[:300]}")
                    for tag in n.tags:
                        desc_parts.append(
                            f"  [{tag.get('rel_type', '')}] -> {tag.get('target_name', '')}"
                        )
                description = "\n".join(desc_parts) if desc_parts else f"Nội dung học {subject_name}"

            events.append({
                "summary": summary[:250],
                "location": "Online",
                "description": description,
                "aggregated_content": result.aggregate_text if result.aggregate_text else description,
                "checkpoint_node_id": result.checkpoint_node_id if result.checkpoint_node_id else "root",
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