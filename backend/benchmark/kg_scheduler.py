from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class KGNode:
    identity: int
    node_id: str
    name: str
    description: str
    node_type: str
    level: int
    chunk_ids: list[str]
    labels: list[str]
    tags: list[dict]


@dataclass
class KGRelationship:
    identity: int
    start_identity: int
    end_identity: int
    rel_type: str
    description: str


@dataclass
class KGScheduleResult:
    session_index: int
    checkpoint_node_id: str
    weight: float
    nodes: list[KGNode]
    relationships: list[KGRelationship]
    context_nodes: list[KGNode]
    aggregate_text: str


class KnowledgeGraphScheduler:
    def __init__(self, nodes: list[KGNode], relationships: list[KGRelationship]) -> None:
        self._nodes = {node.identity: node for node in nodes}
        self._relationships = relationships
        self._adj: dict[int, list[int]] = defaultdict(list)
        self._incoming: dict[int, int] = defaultdict(int)
        for rel in relationships:
            self._adj[rel.start_identity].append(rel.end_identity)
            self._incoming[rel.end_identity] += 1

    def schedule(self, session_weights: list[float], checkpoint_node_id: str | None = None) -> list[KGScheduleResult]:
        ordered = self._bfs_order()
        start_idx = 0
        if checkpoint_node_id:
            for index, node in enumerate(ordered):
                if node.node_id == checkpoint_node_id:
                    start_idx = index + 1
                    break

        remaining = ordered[start_idx:]
        if not remaining:
            return []

        groups = self._distribute(remaining, session_weights)
        studied = {node.identity for node in ordered[:start_idx]}
        results: list[KGScheduleResult] = []

        for session_index, (weight, session_nodes) in enumerate(zip(session_weights, groups), start=1):
            session_ids = {node.identity for node in session_nodes}
            all_known = session_ids | studied
            relationships: list[KGRelationship] = []
            context_ids: set[int] = set()

            for rel in self._relationships:
                touches_session = rel.start_identity in session_ids or rel.end_identity in session_ids
                both_known = rel.start_identity in all_known and rel.end_identity in all_known
                if touches_session and both_known:
                    relationships.append(rel)
                    if rel.start_identity not in session_ids:
                        context_ids.add(rel.start_identity)
                    if rel.end_identity not in session_ids:
                        context_ids.add(rel.end_identity)

            aggregate_text = self._build_aggregate_text(session_nodes, relationships)
            checkpoint = session_nodes[-1].node_id if session_nodes else (ordered[start_idx - 1].node_id if start_idx else "root")
            results.append(
                KGScheduleResult(
                    session_index=session_index,
                    checkpoint_node_id=checkpoint,
                    weight=weight,
                    nodes=session_nodes,
                    relationships=relationships,
                    context_nodes=[self._nodes[node_id] for node_id in sorted(context_ids)],
                    aggregate_text=aggregate_text,
                )
            )
            studied |= session_ids
        return results

    def _bfs_order(self) -> list[KGNode]:
        roots = [node for node in self._nodes.values() if self._incoming[node.identity] == 0]
        if not roots:
            min_incoming = min((self._incoming.get(node.identity, 0) for node in self._nodes.values()), default=0)
            roots = [node for node in self._nodes.values() if self._incoming.get(node.identity, 0) == min_incoming]

        visited: set[int] = set()
        queue: deque[KGNode] = deque(sorted(roots, key=lambda node: (node.level, node.identity)))
        ordered: list[KGNode] = []

        while queue:
            node = queue.popleft()
            if node.identity in visited:
                continue
            visited.add(node.identity)
            ordered.append(node)
            for child_id in sorted(self._adj.get(node.identity, []), key=lambda identity: (self._nodes[identity].level, identity)):
                if child_id not in visited:
                    queue.append(self._nodes[child_id])

        for node in sorted(self._nodes.values(), key=lambda item: (item.level, item.identity)):
            if node.identity not in visited:
                ordered.append(node)
        return ordered

    @staticmethod
    def _distribute(nodes: list[KGNode], weights: list[float]) -> list[list[KGNode]]:
        total_weight = sum(weights)
        quotas = [weight / total_weight * len(nodes) for weight in weights]
        floors = [int(quota) for quota in quotas]
        remainders = sorted(((quotas[index] - floors[index], index) for index in range(len(weights))), reverse=True)
        leftover = len(nodes) - sum(floors)
        for offset in range(leftover):
            floors[remainders[offset][1]] += 1

        result: list[list[KGNode]] = []
        cursor = 0
        for count in floors:
            result.append(nodes[cursor:cursor + count])
            cursor += count
        return result

    def _build_aggregate_text(self, nodes: list[KGNode], relationships: list[KGRelationship]) -> str:
        node_lines = [f"- {node.name}: {node.description}" if node.description else f"- {node.name}" for node in nodes]
        relation_lines = []
        for rel in relationships:
            start_name = self._nodes[rel.start_identity].name
            end_name = self._nodes[rel.end_identity].name
            relation_lines.append(f"[{rel.rel_type}] {start_name} -> {end_name}")
        parts = ["Nội dung buổi học hôm nay bao gồm:", "\n".join(node_lines)]
        if relation_lines:
            parts.extend(["Các mối quan hệ giữa các nội dung:", "\n".join(relation_lines)])
        return "\n".join(part for part in parts if part)
