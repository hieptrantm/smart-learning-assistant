# ============================================================
# scheduler.py - Divide tree nodes into study sessions
# ============================================================

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional
from app.llm.base import BaseLLM
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

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
    aggregate_text: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

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
            
            # Generate title and description via LLM if client is available
            title = None
            description = None
            if self._llm_client:
                nodes_text = "\n".join(
                        f"- {n.name}" + (f": {n.description}" if n.description else "")
                        for n in nodes_in_session
                    )
                rels_text = "\n".join(
                        f"  [{r.rel_type}] {self._nodes[r.start_identity].name} -> {self._nodes[r.end_identity].name}"
                        for r in rels
                        if r.start_identity in self._nodes and r.end_identity in self._nodes
                    )
                
                aggregate_text = f"Nội dung buổi học hôm nay bao gồm:\n{nodes_text}"
                if rels_text:
                    aggregate_text += f"\nCác mối quan hệ giữa các nội dung:\n{rels_text}"
                
                try:
                    title_response = await self._llm_client.ainvoke([
                        SystemMessage(content=gen_title_prompt),
                        HumanMessage(content=aggregate_text),
                    ])
                    title = title_response.content.strip() if hasattr(title_response, "content") else str(title_response).strip()
                except Exception as e:
                    logger.warning(
                        f"[TreeScheduler] LLM title generation failed for session {idx + 1}: {e}"
                    )

                try:
                    desc_response = await self._llm_client.ainvoke([
                        SystemMessage(content=gen_desc_prompt),
                        HumanMessage(content=gen_qa_prompt.format(
                            nodes=aggregate_text
                        )),
                    ])
                    description = desc_response.content.strip() if hasattr(desc_response, "content") else str(desc_response).strip()
                except Exception as e:
                    logger.warning(
                        f"[TreeScheduler] LLM description generation failed for session {idx + 1}: {e}"
                    )

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
                f"Session {idx + 1}: \n"
                f"  checkpoint_node_id='{results[-1].checkpoint_node_id}'\n"
                f"  Nodes name: {[n.name for n in nodes_in_session]}\n"
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