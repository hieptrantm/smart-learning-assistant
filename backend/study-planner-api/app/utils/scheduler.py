# ============================================================
# scheduler.py - Divide tree nodes into study sessions
# ============================================================

import asyncio
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional
from app.llm.base import BaseLLM
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from app.config import QDRANT_HOST, QDRANT_PORT

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Data models ───────────────────────────────────────────────

@dataclass
class NodeInfo:
    """Parsed node from Neo4j path data."""
    identity: int
    node_id: str
    name: str
    description: str
    node_type: str
    level: int
    chunk_ids: list[str]
    tags: list[dict]
    labels: list[str]
    element_id: str


@dataclass
class RelationshipInfo:
    """Parsed relationship from Neo4j path segments."""
    identity: int
    start_identity: int
    end_identity: int
    rel_type: str
    description: str
    element_id: str


@dataclass
class SessionResult:
    """Output for one study session."""
    session_index: int
    checkpoint_node_id: str
    weight: float
    nodes: list[NodeInfo]
    relationships: list[RelationshipInfo]
    context_nodes: list[NodeInfo]
    checkpoint_chunk_id: Optional[str] = None
    aggregate_text: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ChunkEntry:
    key: str
    checkpoint_id: str
    title: str
    text: str
    source_node_id: str = ""
    source_identity: int = -1
    raw_text: str = ""
    low_level_contexts: list[str] = field(default_factory=list)
    high_level_contexts: list[str] = field(default_factory=list)

gen_title_prompt = """Bạn là một chuyên gia giáo dục và tổng hợp kiến thức. Nhiệm vụ của bạn là viết một tiêu đề ngắn gọn (7-10 từ) cho buổi học hôm nay. Chỉ gen ra tiêu đề bài học, không ghi gì thêm.
"""    
gen_desc_prompt = """
Bạn là một chuyên gia giáo dục và tổng hợp kiến thức. Nhiệm vụ của bạn là viết mô tả ngắn gọn (1-2 câu) về nội dung của bài học hôm nay. Chỉ tạo mô tả thành một đoạn không ghi gì thêm
"""
gen_qa_prompt = """
Nội dung buổi học hôm nay bao gồm:
{nodes} 
"""


# ── Parser ────────────────────────────────────────────────────

class TreeScheduler:
    """
    Divides tree nodes into study sessions using BFS order and
    proportional weight distribution.

    Args:
        raw_paths:  The list of path objects from the Neo4j query
                    (the JSON you export from the browser table).
    """

    def __init__(self, raw_paths: list[dict], llm_client: Optional[BaseLLM] = None):
        self._nodes: dict[int, NodeInfo] = {}      
        self._edges: dict[int, RelationshipInfo] = {}
        self._adj: dict[int, list[int]] = defaultdict(list)   # parent identity → [child identity]
        self._edge_by_endpoints: dict[tuple[int, int], RelationshipInfo] = {}
        self._llm_client = llm_client
        self._parse(raw_paths)

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    async def schedule(
        self,
        session_weights: list[float],
        checkpoint_node_id: Optional[str] = None,
    ) -> list[SessionResult]:
        """
        Main function: split nodes into study sessions.

        Args:
            session_weights:    List of weights (hours) per session, e.g. [2, 2, 2].
                                The proportion of each weight determines how many nodes
                                go into that session.
            checkpoint_node_id: node_id string of the last-studied node.
                                All nodes up to and including this node in BFS order
                                are skipped; remaining nodes are redistributed across
                                the sessions proportionally.

        Returns:
            List of SessionResult, one per session.
        """
        # Test
        # checkpoint_node_id = 'node_4255414272310442917'
        if not session_weights:
            raise ValueError("session_weights must be a non-empty list.")
        if any(w <= 0 for w in session_weights):
            raise ValueError("All session weights must be positive.")

        # 1. BFS-ordered node list
        bfs_ordered = self._bfs_order()
        
        logger.info(f"checkpoint_node_id received: {checkpoint_node_id!r}")

        # 2. Apply checkpoint: skip already-studied nodes
        start_idx = 0
        if checkpoint_node_id:
            for i, node in enumerate(bfs_ordered):
                if node.node_id == checkpoint_node_id:
                    start_idx = i + 1
                    break
            else:
                raise ValueError(
                    f"checkpoint_node_id='{checkpoint_node_id}' not found in the graph."
                )

        remaining_nodes = [
            n for n in bfs_ordered[start_idx:]
            if n.node_type != "ROOT" and "TreeRoot" not in n.labels
        ]

        if not remaining_nodes:
            return []
        
        logger.info(
            f"All filtered Nodes with BFS Order: {[(n.node_id, n.name) for n in remaining_nodes]}"
        )

        # 3. Distribute nodes proportionally across sessions
        session_node_lists = self._distribute(remaining_nodes, session_weights)

        # 4. Build SessionResult with context relationships
        results: list[SessionResult] = []
        # Always include root in studied_identities so root→child edges are contextual
        root_identities = {
            n.identity for n in self._nodes.values()
            if "TreeRoot" in n.labels or n.node_type == "ROOT"
        }
        studied_identities: set[int] = {n.identity for n in bfs_ordered[:start_idx]} | root_identities

        # Fallback: root node_id for sessions with no nodes
        root_node_id = "root"
        for n in self._nodes.values():
            if "TreeRoot" in n.labels or n.node_type == "ROOT":
                root_node_id = n.node_id
                break
            
        logger.info(f"Root node_id determined as '{root_node_id}' for sessions with no nodes.")

        for idx, (weight, nodes_in_session) in enumerate(
            zip(session_weights, session_node_lists)
        ):
            session_identities = {n.identity for n in nodes_in_session}
            all_known = studied_identities | session_identities

            # Collect every relationship where at least one endpoint is in this
            # session AND the other endpoint is in all_known (i.e. already
            # studied or in the current session → full context, no orphan edges).
            rels: list[RelationshipInfo] = []
            context_identity_needed: set[int] = set()

            for rel in self._edges.values():
                touches_session = (
                    rel.start_identity in session_identities
                    or rel.end_identity in session_identities
                )
                both_known = (
                    rel.start_identity in all_known
                    and rel.end_identity in all_known
                )
                if touches_session and both_known:
                    rels.append(rel)
                    # If the other endpoint is NOT in the current session,
                    # it is a context node (parent / sibling from previous session).
                    if rel.start_identity not in session_identities:
                        context_identity_needed.add(rel.start_identity)
                    if rel.end_identity not in session_identities:
                        context_identity_needed.add(rel.end_identity)

            context_nodes = [
                self._nodes[i]
                for i in context_identity_needed
                if i in self._nodes
            ]

            nodes_text = "\n".join(
                f"- {n.name}" + (f": {n.description}" if n.description else "")
                for n in nodes_in_session
            )
            rels_text = "\n".join(
                f"  [{r.rel_type}] {self._nodes[r.start_identity].name} -> {self._nodes[r.end_identity].name}"
                for r in rels
                if r.start_identity in self._nodes and r.end_identity in self._nodes
            )
            aggregate_text = "Nội dung buổi học hôm nay bao gồm:\n"
            aggregate_text += nodes_text if nodes_text else "- Chưa có nội dung mới trong buổi này"
            if rels_text:
                aggregate_text += f"\nCác mối quan hệ giữa các nội dung:\n{rels_text}"
            
            # Generate title and description via LLM if client is available
            title = None
            description = None
            if self._llm_client and nodes_in_session:
                title_task = self._llm_client.ainvoke([
                    SystemMessage(content=gen_title_prompt),
                    HumanMessage(content=aggregate_text),
                ])
                desc_task = self._llm_client.ainvoke([
                    SystemMessage(content=gen_desc_prompt),
                    HumanMessage(content=gen_qa_prompt.format(nodes=aggregate_text)),
                ])
                title_response, desc_response = await asyncio.gather(
                    title_task,
                    desc_task,
                    return_exceptions=True,
                )
                if isinstance(title_response, Exception):
                    logger.warning(
                        "[TreeScheduler] LLM title generation failed for session %s: %s",
                        idx + 1,
                        title_response,
                    )
                else:
                    title = title_response.content.strip() if hasattr(title_response, "content") else str(title_response).strip()

                if isinstance(desc_response, Exception):
                    logger.warning(
                        "[TreeScheduler] LLM description generation failed for session %s: %s",
                        idx + 1,
                        desc_response,
                    )
                else:
                    description = desc_response.content.strip() if hasattr(desc_response, "content") else str(desc_response).strip()

            results.append(SessionResult(
                session_index=idx + 1,
                checkpoint_node_id=nodes_in_session[-1].node_id if nodes_in_session else root_node_id,
                weight=weight,
                title=title,
                description=description,
                aggregate_text=aggregate_text,
                nodes=nodes_in_session,
                relationships=rels,
                context_nodes=context_nodes,
            ))
            
            logger.info(
                "[TreeScheduler] Session %s | checkpoint_node_id=%r | nodes=%s | context_nodes=%s",
                idx + 1,
                results[-1].checkpoint_node_id,
                [n.name for n in nodes_in_session],
                [n.name for n in context_nodes],
            )

            # Nodes from this session become "studied" for the next session
            studied_identities |= session_identities

        return results

    # ──────────────────────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────────────────────

    def _parse(self, raw_paths: list[dict]) -> None:
        """Extract unique nodes and edges from the list of Neo4j path objects."""
        for path_item in raw_paths:
            p = path_item.get("p", path_item)   # handle both {"p": ...} and bare path
            for segment in p.get("segments", []):
                self._register_node(segment["start"])
                self._register_node(segment["end"])
                self._register_edge(segment["relationship"])

    def _register_node(self, raw: dict) -> None:
        identity = raw["identity"]
        if identity in self._nodes:
            return

        props = raw.get("properties", {})
        tags_raw = props.get("tags", "[]")
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except json.JSONDecodeError:
                tags = []
        else:
            tags = tags_raw if isinstance(tags_raw, list) else []

        self._nodes[identity] = NodeInfo(
            identity=identity,
            node_id=props.get("node_id", str(identity)),
            name=props.get("name", ""),
            description=props.get("description", ""),
            node_type=props.get("node_type", "UNKNOWN"),
            level=props.get("level", -1),
            chunk_ids=props.get("chunk_ids", []),
            tags=tags,
            labels=raw.get("labels", []),
            element_id=raw.get("elementId", ""),
        )

    def _register_edge(self, raw: dict) -> None:
        identity = raw["identity"]
        if identity in self._edges:
            return

        props = raw.get("properties", {})
        rel = RelationshipInfo(
            identity=identity,
            start_identity=raw["start"],
            end_identity=raw["end"],
            rel_type=raw.get("type", ""),
            description=props.get("description", ""),
            element_id=raw.get("elementId", ""),
        )
        self._edges[identity] = rel
        self._adj[rel.start_identity].append(rel.end_identity)
        self._edge_by_endpoints[(rel.start_identity, rel.end_identity)] = rel

    # ──────────────────────────────────────────────────────────
    # BFS
    # ──────────────────────────────────────────────────────────

    def _bfs_order(self) -> list[NodeInfo]:
        """
        BFS traversal starting from the ROOT node (level == 0 and label
        contains 'TreeRoot').  Returns nodes in visit order.
        """
        # Find root(s)
        roots = [
            n for n in self._nodes.values()
            if "TreeRoot" in n.labels or n.node_type == "ROOT"
        ]
        if not roots:
            # Fallback: node with no incoming edges
            children = {rel.end_identity for rel in self._edges.values()}
            roots = [n for n in self._nodes.values() if n.identity not in children]

        if not roots:
            raise RuntimeError("Cannot determine root node from the graph data.")

        visited: set[int] = set()
        queue: deque[NodeInfo] = deque()
        ordered: list[NodeInfo] = []

        for root in sorted(roots, key=lambda n: n.level):
            if root.identity not in visited:
                visited.add(root.identity)
                queue.append(root)

        while queue:
            node = queue.popleft()
            ordered.append(node)
            # Sort children by (level, identity) for deterministic BFS order
            children = sorted(
                self._adj.get(node.identity, []),
                key=lambda cid: (self._nodes[cid].level, self._nodes[cid].identity),
            )
            for child_id in children:
                if child_id not in visited:
                    visited.add(child_id)
                    queue.append(self._nodes[child_id])

        return ordered

    # ──────────────────────────────────────────────────────────
    # Weight-proportional distribution
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _distribute(
        nodes: list[NodeInfo],
        weights: list[float],
    ) -> list[list[NodeInfo]]:
        """
        Distribute `nodes` across sessions proportionally to `weights`.
        Uses the "largest remainder" method so total always equals len(nodes).
        """
        n_nodes = len(nodes)
        n_sessions = len(weights)
        total_weight = sum(weights)

        # Exact (fractional) quota per session
        quotas = [w / total_weight * n_nodes for w in weights]

        # Floor allocation
        floors = [int(q) for q in quotas]
        remainders = [(quotas[i] - floors[i], i) for i in range(n_sessions)]

        # Distribute leftover slots to sessions with largest remainders
        leftover = n_nodes - sum(floors)
        remainders.sort(key=lambda x: -x[0])
        for k in range(leftover):
            floors[remainders[k][1]] += 1

        # Slice the node list
        result: list[list[NodeInfo]] = []
        cursor = 0
        for count in floors:
            result.append(nodes[cursor: cursor + count])
            cursor += count
        return result

    # ──────────────────────────────────────────────────────────
    # Utility / debug
    # ──────────────────────────────────────────────────────────

    def get_node_by_id(self, node_id: str) -> Optional[NodeInfo]:
        for n in self._nodes.values():
            if n.node_id == node_id:
                return n
        return None

    def summary(self) -> str:
        lines = [
            f"TreeScheduler: {len(self._nodes)} nodes, {len(self._edges)} edges",
        ]
        for node in sorted(self._nodes.values(), key=lambda n: n.level):
            lines.append(
                f"  [L{node.level}] {node.name} ({node.node_type}) — id={node.node_id}"
            )
        return "\n".join(lines)


class ChunkScheduler(TreeScheduler):
    """Distribute study sessions by Qdrant chunk ordering and chunk-linked contexts."""

    def __init__(
        self,
        raw_paths: Optional[list[dict]] = None,
        llm_client: Optional[BaseLLM] = None,
        qdrant_client: Optional[QdrantClient] = None,
        qdrant_host: str = QDRANT_HOST,
        qdrant_port: int = QDRANT_PORT,
        raw_collection: str = "raw_chunks",
        low_level_collection: str = "low-level-retrieval",
        high_level_collection: str = "high-level-retrieval",
    ):
        super().__init__(raw_paths or [], llm_client=llm_client)
        self._qdrant = qdrant_client or QdrantClient(host=qdrant_host, port=qdrant_port)
        self._raw_collection = raw_collection
        self._low_level_collection = low_level_collection
        self._high_level_collection = high_level_collection

    async def get_schedulable_unit_count(self, subject_keys: list[str]) -> int:
        entries = await asyncio.to_thread(self._fetch_chunk_entries_from_qdrant, subject_keys)
        return len(entries)

    async def schedule(
        self,
        session_weights: list[float],
        checkpoint_chunk_id: Optional[str] = None,
        subject_keys: Optional[list[str]] = None,
    ) -> list[SessionResult]:
        if not session_weights:
            raise ValueError("session_weights must be a non-empty list.")
        if any(weight <= 0 for weight in session_weights):
            raise ValueError("All session weights must be positive.")
        if not subject_keys:
            raise ValueError("subject_keys must be provided to load chunks from Qdrant.")

        all_entries = await asyncio.to_thread(self._fetch_chunk_entries_from_qdrant, subject_keys)
        if not all_entries:
            return []

        start_idx = self._resolve_checkpoint(checkpoint_chunk_id, all_entries)
        remaining_entries = all_entries[start_idx:]
        if not remaining_entries:
            return []

        session_entry_lists = self._distribute(remaining_entries, session_weights)
        results: list[SessionResult] = []

        for idx, (weight, session_entries) in enumerate(zip(session_weights, session_entry_lists), start=1):
            session_chunk_ids = [entry.checkpoint_id for entry in session_entries]
            nodes = self._build_nodes_from_entries(session_entries)
            aggregate_text = self._build_chunk_aggregate_text(session_entries)

            title = None
            description = None
            if self._llm_client and session_entries:
                title_task = self._llm_client.ainvoke([
                    SystemMessage(content=gen_title_prompt),
                    HumanMessage(content=aggregate_text),
                ])
                desc_task = self._llm_client.ainvoke([
                    SystemMessage(content=gen_desc_prompt),
                    HumanMessage(content=gen_qa_prompt.format(nodes=aggregate_text)),
                ])
                title_response, desc_response = await asyncio.gather(
                    title_task,
                    desc_task,
                    return_exceptions=True,
                )
                if isinstance(title_response, Exception):
                    logger.warning(
                        "[ChunkScheduler] LLM title generation failed for session %s: %s",
                        idx,
                        title_response,
                    )
                else:
                    title = title_response.content.strip() if hasattr(title_response, "content") else str(title_response).strip()

                if isinstance(desc_response, Exception):
                    logger.warning(
                        "[ChunkScheduler] LLM description generation failed for session %s: %s",
                        idx,
                        desc_response,
                    )
                else:
                    description = desc_response.content.strip() if hasattr(desc_response, "content") else str(desc_response).strip()

            checkpoint = session_entries[-1].checkpoint_id if session_entries else "root"
            results.append(SessionResult(
                session_index=idx,
                checkpoint_node_id=checkpoint,
                checkpoint_chunk_id=checkpoint,
                weight=weight,
                title=title,
                description=description,
                aggregate_text=aggregate_text,
                nodes=nodes,
                relationships=[],
                context_nodes=[],
                chunk_ids=session_chunk_ids,
            ))

        return results

    def _fetch_chunk_entries_from_qdrant(self, subject_keys: list[str]) -> list[ChunkEntry]:
        raw_points = self._scroll_points(self._raw_collection, subject_keys)
        if not raw_points:
            logger.warning("[ChunkScheduler] No raw chunk points found for subject filters: %s", subject_keys)
            return []

        low_points = self._scroll_points(self._low_level_collection, subject_keys)
        high_points = self._scroll_points(self._high_level_collection, subject_keys)

        low_context_map = self._group_contexts_by_chunk(low_points)
        high_context_map = self._group_contexts_by_chunk(high_points)

        entries: list[ChunkEntry] = []
        seen_chunk_ids: set[str] = set()

        sorted_raw = sorted(
            raw_points,
            key=lambda point: self._chunk_sort_key(self._extract_chunk_id_from_payload(point.get("payload", {}))),
        )

        for point in sorted_raw:
            payload = point.get("payload", {})
            chunk_id = self._extract_chunk_id_from_payload(payload)
            if not chunk_id or chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)

            raw_text = self._extract_raw_text(payload)
            low_contexts = low_context_map.get(chunk_id, [])
            high_contexts = high_context_map.get(chunk_id, [])
            title = self._extract_title(payload, chunk_id)
            summary = self._build_chunk_summary(raw_text, low_contexts, high_contexts)

            entries.append(ChunkEntry(
                key=self._chunk_key(chunk_id),
                checkpoint_id=chunk_id,
                title=title,
                text=summary,
                raw_text=raw_text,
                low_level_contexts=low_contexts,
                high_level_contexts=high_contexts,
            ))

        return entries

    def _scroll_points(self, collection_name: str, subject_keys: list[str], limit: int = 256) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = None
        qdrant_filter = self._build_subject_filter(subject_keys)

        while True:
            points, next_offset = self._qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
                limit=limit,
                offset=offset,
            )
            for point in points:
                records.append({
                    "id": getattr(point, "id", None),
                    "payload": getattr(point, "payload", {}) or {},
                })
            if next_offset is None:
                break
            offset = next_offset

        return records

    @staticmethod
    def _build_subject_filter(subject_keys: list[str]) -> Optional[Filter]:
        candidates = [str(value).strip() for value in subject_keys if value is not None and str(value).strip()]
        if not candidates:
            return None

        normalized = list(dict.fromkeys(candidates))
        if len(normalized) == 1:
            return Filter(must=[FieldCondition(key="metadata.subject_id", match=MatchValue(value=normalized[0]))])

        return Filter(should=[
            FieldCondition(key="metadata.subject_id", match=MatchValue(value=value))
            for value in normalized
        ])

    def _group_contexts_by_chunk(self, points: list[dict[str, Any]]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for point in points:
            payload = point.get("payload", {})
            metadata = payload.get("metadata") or {}
            chunk_ids = self._extract_chunk_ids(metadata)
            if not chunk_ids:
                continue
            context_text = self._format_context_payload(payload)
            if not context_text:
                continue
            for chunk_id in chunk_ids:
                grouped[chunk_id].append(context_text)
        return dict(grouped)

    @staticmethod
    def _extract_chunk_ids(metadata: dict[str, Any]) -> list[str]:
        chunk_ids: list[str] = []
        single_chunk_id = metadata.get("chunk_id")
        if isinstance(single_chunk_id, str) and single_chunk_id.strip():
            chunk_ids.append(single_chunk_id.strip())

        multiple_chunk_ids = metadata.get("chunk_ids", [])
        if isinstance(multiple_chunk_ids, list):
            chunk_ids.extend(
                item.strip()
                for item in multiple_chunk_ids
                if isinstance(item, str) and item.strip()
            )
        elif isinstance(multiple_chunk_ids, str) and multiple_chunk_ids.strip():
            chunk_ids.append(multiple_chunk_ids.strip())

        return list(dict.fromkeys(chunk_ids))

    @staticmethod
    def _extract_chunk_id_from_payload(payload: dict[str, Any]) -> str:
        metadata = payload.get("metadata") or {}
        chunk_id = metadata.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id.strip():
            return chunk_id.strip()

        chunk_ids = metadata.get("chunk_ids") or []
        if isinstance(chunk_ids, list):
            for item in chunk_ids:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        elif isinstance(chunk_ids, str) and chunk_ids.strip():
            return chunk_ids.strip()
        return ""

    @staticmethod
    def _extract_raw_text(payload: dict[str, Any]) -> str:
        page_content = payload.get("page_content")
        if isinstance(page_content, str) and page_content.strip():
            return page_content.strip()

        metadata = payload.get("metadata") or {}
        description = metadata.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
        return ""

    @staticmethod
    def _extract_title(payload: dict[str, Any], fallback_chunk_id: str) -> str:
        metadata = payload.get("metadata") or {}
        for key in ("theme", "source_entity", "target_entity", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return fallback_chunk_id

    def _resolve_checkpoint(self, checkpoint_chunk_id: Optional[str], entries: list[ChunkEntry]) -> int:
        if not checkpoint_chunk_id:
            return 0

        for index, entry in enumerate(entries):
            if checkpoint_chunk_id in {entry.checkpoint_id, entry.key}:
                return index + 1

        raise ValueError(
            f"checkpoint_chunk_id='{checkpoint_chunk_id}' not found in qdrant chunk ordering."
        )

    @staticmethod
    def _build_nodes_from_entries(session_entries: list[ChunkEntry]) -> list[NodeInfo]:
        nodes: list[NodeInfo] = []
        for idx, entry in enumerate(session_entries, start=1):
            nodes.append(NodeInfo(
                identity=idx,
                node_id=entry.checkpoint_id,
                name=entry.title,
                description=entry.text,
                node_type="CHUNK",
                level=1,
                chunk_ids=[entry.checkpoint_id],
                tags=[],
                labels=["Chunk"],
                element_id=entry.key,
            ))
        return nodes

    @staticmethod
    def _build_chunk_summary(raw_text: str, low_contexts: list[str], high_contexts: list[str]) -> str:
        parts = []
        if raw_text:
            preview = raw_text[:700] + ("..." if len(raw_text) > 700 else "")
            parts.append(f"Raw chunk: {preview}")
        if low_contexts:
            parts.append("Low-level context: " + " | ".join(low_contexts[:5]))
        if high_contexts:
            parts.append("High-level context: " + " | ".join(high_contexts[:5]))
        return "\n".join(parts) if parts else "Không có nội dung cho chunk này"

    @staticmethod
    def _format_context_payload(payload: dict[str, Any]) -> str:
        metadata = payload.get("metadata") or {}
        page_content = payload.get("page_content") if isinstance(payload.get("page_content"), str) else ""
        theme = metadata.get("theme")
        description = metadata.get("description")
        source_entity = metadata.get("source_entity")
        target_entity = metadata.get("target_entity")
        relation_type = metadata.get("relation_type")

        if isinstance(theme, str) and theme.strip() and isinstance(description, str) and description.strip():
            return f"{theme.strip()}: {description.strip()}"
        if isinstance(source_entity, str) and source_entity.strip() and isinstance(target_entity, str) and target_entity.strip():
            rel = relation_type.strip() if isinstance(relation_type, str) and relation_type.strip() else "RELATED_TO"
            return f"{source_entity.strip()} [{rel}] {target_entity.strip()}"
        if isinstance(description, str) and description.strip():
            return description.strip()
        if page_content and page_content.strip():
            preview = page_content.strip()
            return preview[:300] + ("..." if len(preview) > 300 else "")
        return ""

    @staticmethod
    def _build_chunk_aggregate_text(session_entries: list[ChunkEntry]) -> str:
        if not session_entries:
            return "Nội dung buổi học hôm nay bao gồm:\n- Chưa có nội dung mới trong buổi này"

        lines = ["Nội dung buổi học hôm nay bao gồm:"]
        for entry in session_entries:
            lines.append(f"- Chunk: {entry.checkpoint_id}")
            if entry.raw_text:
                raw_preview = entry.raw_text[:600] + ("..." if len(entry.raw_text) > 600 else "")
                lines.append(f"  Raw: {raw_preview}")
            if entry.low_level_contexts:
                lines.append("  Low-level:")
                for item in entry.low_level_contexts[:5]:
                    lines.append(f"    - {item}")
            if entry.high_level_contexts:
                lines.append("  High-level:")
                for item in entry.high_level_contexts[:5]:
                    lines.append(f"    - {item}")

        return "\n".join(lines)

    @staticmethod
    def _chunk_key(chunk_id: str) -> str:
        return f"chunk::{chunk_id}"

    @staticmethod
    def _chunk_sort_key(chunk_id: str) -> tuple[str, int, str]:
        if not chunk_id:
            return ("", -1, "")

        match = re.match(r"^(.*?_chunk_)(\d+)$", chunk_id, flags=re.IGNORECASE)
        if match:
            prefix, number = match.groups()
            return (prefix.lower(), int(number), chunk_id.lower())

        trailing = re.search(r"(\d+)$", chunk_id)
        if trailing:
            number = int(trailing.group(1))
            prefix = chunk_id[: trailing.start()].lower()
            return (prefix, number, chunk_id.lower())

        return (chunk_id.lower(), -1, chunk_id.lower())

if __name__ == "__main__":
    json_file = "test.json"

    with open(json_file, "r", encoding="utf-8") as f:
        raw_paths = json.load(f)

    scheduler = TreeScheduler(raw_paths)
    checkpoint_node_id = None  
    session_weights = [1, 2, 2]
    
    res = scheduler.schedule(session_weights, checkpoint_node_id)
    for session in res:
        print(f"Session {session.session_index} (weight={session.weight}):")
        for node in session.nodes:
            print(f"  - {node.name} ({node.node_id})")
        print(f"  Relationships: {len(session.relationships)}")
        print(f"  Context nodes: {len(session.context_nodes)}")
        print()