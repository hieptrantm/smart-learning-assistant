from __future__ import annotations

import json
import logging
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.base import BaseLLM

logger = logging.getLogger(__name__)

GEN_TITLE_PROMPT = """Bạn là một chuyên gia giáo dục và tổng hợp kiến thức. Nhiệm vụ của bạn là viết một tiêu đề ngắn gọn (7-10 từ) cho buổi học hôm nay. Chỉ gen ra tiêu đề bài học, không ghi gì thêm.
"""
GEN_DESC_PROMPT = """
Bạn là một chuyên gia giáo dục và tổng hợp kiến thức. Nhiệm vụ của bạn là viết mô tả ngắn gọn (1-2 câu) về nội dung của bài học hôm nay. Chỉ tạo mô tả thành một đoạn không ghi gì thêm
"""
GEN_QA_PROMPT = """
Nội dung buổi học hôm nay bao gồm:
{nodes}
"""


@dataclass
class GraphNodeInfo:
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
class GraphRelationshipInfo:
    identity: int
    start_identity: int
    end_identity: int
    rel_type: str
    description: str
    element_id: str


@dataclass
class GraphSessionResult:
    session_index: int
    checkpoint_node_id: str
    weight: float
    nodes: list[GraphNodeInfo]
    relationships: list[GraphRelationshipInfo]
    context_nodes: list[GraphNodeInfo]
    aggregate_text: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class GraphScheduler:
    """Build study sessions directly from the raw Entity knowledge graph."""

    def __init__(
        self,
        nodes: list[GraphNodeInfo],
        relationships: list[GraphRelationshipInfo],
        llm_client: Optional[BaseLLM] = None,
    ) -> None:
        self._nodes = {node.identity: node for node in nodes}
        self._relationships = relationships
        self._adj: dict[int, list[int]] = defaultdict(list)
        self._incoming: dict[int, int] = defaultdict(int)
        self._llm_client = llm_client

        for rel in relationships:
            self._adj[rel.start_identity].append(rel.end_identity)
            self._incoming[rel.end_identity] += 1

    async def schedule(
        self,
        session_weights: list[float],
        checkpoint_node_id: Optional[str] = None,
    ) -> list[GraphSessionResult]:
        if not session_weights:
            raise ValueError("session_weights must be a non-empty list.")
        if any(weight <= 0 for weight in session_weights):
            raise ValueError("All session weights must be positive.")

        ordered = self._bfs_order()
        start_idx = 0
        if checkpoint_node_id:
            for index, node in enumerate(ordered):
                if node.node_id == checkpoint_node_id:
                    start_idx = index + 1
                    break
            else:
                raise ValueError(f"checkpoint_node_id='{checkpoint_node_id}' not found in the graph.")

        remaining = ordered[start_idx:]
        if not remaining:
            return []

        session_node_lists = self._distribute(remaining, session_weights)
        studied_identities = {node.identity for node in ordered[:start_idx]}
        fallback_checkpoint = ordered[start_idx - 1].node_id if start_idx else "graph_root"
        results: list[GraphSessionResult] = []

        for idx, (weight, nodes_in_session) in enumerate(zip(session_weights, session_node_lists), start=1):
            session_identities = {node.identity for node in nodes_in_session}
            all_known = studied_identities | session_identities

            rels: list[GraphRelationshipInfo] = []
            context_identity_needed: set[int] = set()
            for rel in self._relationships:
                touches_session = rel.start_identity in session_identities or rel.end_identity in session_identities
                both_known = rel.start_identity in all_known and rel.end_identity in all_known
                if touches_session and both_known:
                    rels.append(rel)
                    if rel.start_identity not in session_identities:
                        context_identity_needed.add(rel.start_identity)
                    if rel.end_identity not in session_identities:
                        context_identity_needed.add(rel.end_identity)

            context_nodes = [self._nodes[node_id] for node_id in sorted(context_identity_needed) if node_id in self._nodes]

            nodes_text = "\n".join(
                f"- {node.name}" + (f": {node.description}" if node.description else "")
                for node in nodes_in_session
            )
            rels_text = "\n".join(
                f"  [{rel.rel_type}] {self._nodes[rel.start_identity].name} -> {self._nodes[rel.end_identity].name}"
                for rel in rels
                if rel.start_identity in self._nodes and rel.end_identity in self._nodes
            )
            aggregate_text = "Nội dung buổi học hôm nay bao gồm:\n"
            aggregate_text += nodes_text if nodes_text else "- Chưa có nội dung mới trong buổi này"
            if rels_text:
                aggregate_text += f"\nCác mối quan hệ giữa các nội dung:\n{rels_text}"

            title = None
            description = None
            if self._llm_client and nodes_in_session:
                title_task = self._llm_client.ainvoke([
                    SystemMessage(content=GEN_TITLE_PROMPT),
                    HumanMessage(content=aggregate_text),
                ])
                desc_task = self._llm_client.ainvoke([
                    SystemMessage(content=GEN_DESC_PROMPT),
                    HumanMessage(content=GEN_QA_PROMPT.format(nodes=aggregate_text)),
                ])
                title_response, desc_response = await asyncio.gather(
                    title_task,
                    desc_task,
                    return_exceptions=True,
                )
                if isinstance(title_response, Exception):
                    logger.warning("[GraphScheduler] LLM title generation failed for session %s: %s", idx, title_response)
                else:
                    title = title_response.content.strip() if hasattr(title_response, "content") else str(title_response).strip()

                if isinstance(desc_response, Exception):
                    logger.warning("[GraphScheduler] LLM description generation failed for session %s: %s", idx, desc_response)
                else:
                    description = desc_response.content.strip() if hasattr(desc_response, "content") else str(desc_response).strip()

            checkpoint_value = nodes_in_session[-1].node_id if nodes_in_session else fallback_checkpoint
            results.append(
                GraphSessionResult(
                    session_index=idx,
                    checkpoint_node_id=checkpoint_value,
                    weight=weight,
                    nodes=nodes_in_session,
                    relationships=rels,
                    context_nodes=context_nodes,
                    aggregate_text=aggregate_text,
                    title=title,
                    description=description,
                )
            )
            logger.info(
                "[GraphScheduler] Session %s | checkpoint_node_id=%r | nodes=%s | context_nodes=%s",
                idx,
                checkpoint_value,
                [node.name for node in nodes_in_session],
                [node.name for node in context_nodes],
            )
            studied_identities |= session_identities

        return results

    def _bfs_order(self) -> list[GraphNodeInfo]:
        roots = [node for node in self._nodes.values() if self._incoming[node.identity] == 0]
        if not roots:
            min_incoming = min((self._incoming.get(node.identity, 0) for node in self._nodes.values()), default=0)
            roots = [node for node in self._nodes.values() if self._incoming.get(node.identity, 0) == min_incoming]

        visited: set[int] = set()
        ordered: list[GraphNodeInfo] = []
        queue: deque[GraphNodeInfo] = deque(sorted(roots, key=lambda node: (node.level, node.identity)))

        while queue:
            node = queue.popleft()
            if node.identity in visited:
                continue
            visited.add(node.identity)
            ordered.append(node)
            child_ids = sorted(
                self._adj.get(node.identity, []),
                key=lambda identity: (self._nodes[identity].level, identity),
            )
            for child_id in child_ids:
                if child_id not in visited:
                    queue.append(self._nodes[child_id])

        for node in sorted(self._nodes.values(), key=lambda item: (item.level, item.identity)):
            if node.identity not in visited:
                ordered.append(node)

        return ordered

    @staticmethod
    def _distribute(nodes: list[GraphNodeInfo], weights: list[float]) -> list[list[GraphNodeInfo]]:
        total_weight = sum(weights)
        quotas = [weight / total_weight * len(nodes) for weight in weights]
        floors = [int(quota) for quota in quotas]
        remainders = sorted(((quotas[index] - floors[index], index) for index in range(len(weights))), reverse=True)
        leftover = len(nodes) - sum(floors)

        for offset in range(leftover):
            floors[remainders[offset][1]] += 1

        result: list[list[GraphNodeInfo]] = []
        cursor = 0
        for count in floors:
            result.append(nodes[cursor:cursor + count])
            cursor += count
        return result


def graph_node_from_neo4j(node) -> GraphNodeInfo:
    props = dict(node)
    tags = props.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []

    return GraphNodeInfo(
        identity=node.id,
        node_id=props.get("node_id", f"kg_{node.id}"),
        name=props.get("name", ""),
        description=props.get("description", ""),
        node_type=props.get("type", "ENTITY"),
        level=props.get("level", 0),
        chunk_ids=props.get("chunk_ids", []),
        tags=tags if isinstance(tags, list) else [],
        labels=list(node.labels),
        element_id=node.element_id,
    )


def graph_relationship_from_neo4j(rel) -> GraphRelationshipInfo:
    return GraphRelationshipInfo(
        identity=rel.id,
        start_identity=rel.start_node.id,
        end_identity=rel.end_node.id,
        rel_type=rel.type,
        description=rel.get("description", ""),
        element_id=rel.element_id,
    )
