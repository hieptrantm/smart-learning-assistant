from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore

from benchmark.llm.base import BaseLLM


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
class VectorChunkSessionResult:
    session_index: int
    checkpoint_node_id: str
    weight: float
    nodes: list[object]
    relationships: list[object]
    context_nodes: list[object]
    aggregate_text: str
    chunk_ids: list[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if self.chunk_ids is None:
            self.chunk_ids = []


class VectorChunkPlanner:
    def __init__(
        self,
        nodes_by_chunk_id: dict[str, list[object]],
        raw_chunks: list[dict[str, str]],
        relationships: Optional[list[object]] = None,
        llm_client: Optional[BaseLLM] = None,
    ) -> None:
        self._nodes_by_chunk_id = nodes_by_chunk_id
        self._raw_chunks = raw_chunks
        self._relationships = relationships or []
        self._llm_client = llm_client
        self._nodes_by_identity = self._build_nodes_by_identity(nodes_by_chunk_id)

    async def schedule(self, session_weights: list[float]) -> list[VectorChunkSessionResult]:
        if not self._raw_chunks:
            return []

        chunk_groups = self._distribute(self._raw_chunks, session_weights)
        results: list[VectorChunkSessionResult] = []
        studied_identities: set[int] = set()

        for session_index, (weight, chunks) in enumerate(zip(session_weights, chunk_groups), start=1):
            chunk_ids = [chunk["chunk_id"] for chunk in chunks]
            seen_node_ids: set[int] = set()
            nodes: list[object] = []
            for chunk_id in chunk_ids:
                for node in self._nodes_by_chunk_id.get(chunk_id, []):
                    if node.identity in seen_node_ids:
                        continue
                    seen_node_ids.add(node.identity)
                    nodes.append(node)

            session_identities = {node.identity for node in nodes}
            all_known = studied_identities | session_identities
            relationships: list[object] = []
            context_identity_needed: set[int] = set()
            for rel in self._relationships:
                touches_session = rel.start_identity in session_identities or rel.end_identity in session_identities
                both_known = rel.start_identity in all_known and rel.end_identity in all_known
                if not (touches_session and both_known):
                    continue
                relationships.append(rel)
                if rel.start_identity not in session_identities:
                    context_identity_needed.add(rel.start_identity)
                if rel.end_identity not in session_identities:
                    context_identity_needed.add(rel.end_identity)
            context_nodes = [
                self._nodes_by_identity[node_id]
                for node_id in sorted(context_identity_needed)
                if node_id in self._nodes_by_identity
            ]

            aggregate_text = self._build_aggregate_text(chunks)
            title = None
            description = None
            session_chunk_ids = list(chunk_ids)
            if self._llm_client and chunks:
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
                if not isinstance(title_response, Exception):
                    title = title_response.content.strip() if hasattr(title_response, "content") else str(title_response).strip()
                if not isinstance(desc_response, Exception):
                    description = desc_response.content.strip() if hasattr(desc_response, "content") else str(desc_response).strip()

            checkpoint = chunk_ids[-1] if chunk_ids else f"vector_session_{session_index}"
            results.append(
                VectorChunkSessionResult(
                    session_index=session_index,
                    checkpoint_node_id=checkpoint,
                    weight=weight,
                    nodes=nodes,
                    relationships=relationships,
                    context_nodes=context_nodes,
                    aggregate_text=aggregate_text,
                    chunk_ids=session_chunk_ids,
                    title=title,
                    description=description,
                )
            )
            studied_identities |= session_identities

        return results

    @staticmethod
    def _distribute(chunks: list[dict[str, str]], weights: list[float]) -> list[list[dict[str, str]]]:
        if not weights:
            return [chunks]

        total_weight = sum(weights)
        if total_weight <= 0:
            raise ValueError("session_weights must have a positive total weight")
        quotas = [weight / total_weight * len(chunks) for weight in weights]
        floors = [int(quota) for quota in quotas]
        remainders = sorted(((quotas[index] - floors[index], index) for index in range(len(weights))), reverse=True)
        leftover = len(chunks) - sum(floors)
        for offset in range(leftover):
            floors[remainders[offset][1]] += 1

        groups: list[list[dict[str, str]]] = []
        cursor = 0
        for count in floors:
            groups.append(chunks[cursor:cursor + count])
            cursor += count
        return groups

    @staticmethod
    def _build_aggregate_text(chunks: list[dict[str, str]]) -> str:
        if not chunks:
            return "Nội dung buổi học hôm nay bao gồm:\n- Chưa có nội dung mới trong buổi này"

        lines = ["Nội dung buổi học hôm nay bao gồm:"]
        for chunk in chunks:
            title = chunk.get("title") or chunk.get("chunk_id") or "Chunk"
            text = (chunk.get("text") or "").strip()
            preview = text[:600] + ("..." if len(text) > 600 else "")
            lines.append(f"- {title}: {preview}" if preview else f"- {title}")
        return "\n".join(lines)

    @staticmethod
    def _build_nodes_by_identity(nodes_by_chunk_id: dict[str, list[object]]) -> dict[int, object]:
        by_identity: dict[int, object] = {}
        for nodes in nodes_by_chunk_id.values():
            for node in nodes:
                by_identity[node.identity] = node
        return by_identity