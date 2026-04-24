# ============================================================
# treebase.py - Graph → Tree conversion engine
# ============================================================

import asyncio
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from neo4j import AsyncGraphDatabase
from langchain_core.messages import HumanMessage

import rag_config as config
from llm.base import BaseLLM


# ── Data models ──────────────────────────────────────────────

@dataclass
class GraphNode:
    identity: int
    name: str
    description: str
    chunk_ids: list[str]
    node_type: str
    subject_id: str
    element_id: str


@dataclass
class GraphEdge:
    start_id: int
    end_id: int
    rel_type: str
    description: str


@dataclass
class TreeNode:
    node_id: str
    name: str
    description: str
    node_type: str                      # ROOT | ENTITY
    level: int
    chunk_ids: list[str] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)   # back-edge context


# ── Engine ────────────────────────────────────────────────────

class TreeBasedEngine:
    """
    Converts a subject's knowledge graph (stored in Neo4j) into a
    tree-based representation and indexes it back to Neo4j under a
    new subject_id  (<original>_tree).
    """

    def __init__(self, llm_client: Optional[BaseLLM] = None):
        self.llm = llm_client
        self._driver = AsyncGraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )

    # ── Public entry point ────────────────────────────────────

    async def run(self, subject_id: str) -> str:
        """Full pipeline: fetch graph → build tree → save to Neo4j."""
        nodes, edges = await self._fetch_graph(subject_id)

        # ── DEBUG: show original graph topology ──
        print(f"\n[DEBUG] Nodes ({len(nodes)}):")
        for nid, n in nodes.items():
            print(f"  {nid}: {n.name}")
        print(f"[DEBUG] Edges ({len(edges)}):")
        for e in edges:
            src_name = nodes[e.start_id].name if e.start_id in nodes else e.start_id
            dst_name = nodes[e.end_id].name if e.end_id in nodes else e.end_id
            print(f"  {src_name} --[{e.rel_type}]--> {dst_name}")

        tree_nodes, tree_edges = await self._build_tree(nodes, edges, subject_id)

        # ── DEBUG: show tree result ──
        print(f"\n[DEBUG] Tree nodes ({len(tree_nodes)}):")
        for tn in tree_nodes:
            print(f"  {tn.node_id}: {tn.name} (level={tn.level}, tags={len(tn.tags)})")
            for t in tn.tags:
                print(f"    TAG: --[{t['rel_type']}]--> {t['target_name']}")

        new_subject_id = subject_id + config.TREE_SUBJECT_ID_SUFFIX
        await self._save_tree(new_subject_id, tree_nodes, tree_edges)
        await self._driver.close()
        return new_subject_id

    # ── Step 1 – Fetch graph from Neo4j ───────────────────────

    async def _fetch_graph(self, subject_id: str) -> tuple[dict, list[GraphEdge]]:
        query = """
        MATCH (n:Entity {subject_id: $sid})
        OPTIONAL MATCH (n)-[r]-(m:Entity)
        RETURN n, r, m
        """
        nodes: dict[int, GraphNode] = {}
        edges: list[GraphEdge] = []
        seen_edge_ids: set[str] = set()

        async with self._driver.session() as session:
            result = await session.run(query, sid=subject_id)
            async for record in result:
                n = record["n"]
                self._add_node(nodes, n)
                m, r = record["m"], record["r"]
                if m and r:
                    self._add_node(nodes, m)
                    r_eid = r.element_id
                    if r_eid not in seen_edge_ids:
                        seen_edge_ids.add(r_eid)
                        edges.append(GraphEdge(
                            start_id=r.start_node.element_id if hasattr(r, "start_node") else n.element_id,
                            end_id=r.end_node.element_id if hasattr(r, "end_node") else m.element_id,
                            rel_type=r.type,
                            description=r.get("description", ""),
                        ))

        # Re-map edge ids to integer identity using element_id → identity map
        eid_to_int = {v.element_id: k for k, v in nodes.items()}
        resolved_edges = []
        for e in edges:
            s = eid_to_int.get(e.start_id)
            en = eid_to_int.get(e.end_id)
            if s is not None and en is not None:
                resolved_edges.append(GraphEdge(s, en, e.rel_type, e.description))

        return nodes, resolved_edges

    @staticmethod
    def _add_node(nodes: dict, neo_node) -> None:
        iid = neo_node.element_id
        # Use integer identity when available, else hash element_id
        identity = neo_node.get("identity", hash(iid)) if hasattr(neo_node, "get") else int(iid.split(":")[-1])
        if identity not in nodes:
            props = dict(neo_node)
            nodes[identity] = GraphNode(
                identity=identity,
                name=props.get("name", ""),
                description=props.get("description", ""),
                chunk_ids=props.get("chunk_ids", []),
                node_type=props.get("type", "ENTITY"),
                subject_id=props.get("subject_id", ""),
                element_id=iid,
            )

    # ── Step 2 – Build tree ───────────────────────────────────

    async def _build_tree(
        self,
        nodes: dict[int, GraphNode],
        edges: list[GraphEdge],
        subject_id: str,
    ) -> tuple[list[TreeNode], list[tuple]]:
        """
        BFS from roots:
        - root nodes  = nodes with no incoming edges
        - back-edges  = edges pointing to a node at a lower depth (closer to root)
          → converted to TAG metadata on the source node
        """

        # Build adjacency structures
        in_degree: dict[int, int] = defaultdict(int)
        adj: dict[int, list[tuple[int, GraphEdge]]] = defaultdict(list)   # src → [(dst, edge)]
        edge_map: dict[tuple, GraphEdge] = {}

        for e in edges:
            in_degree[e.end_id] += 1
            adj[e.start_id].append((e.end_id, e))
            edge_map[(e.start_id, e.end_id)] = e

        root_ids = [nid for nid in nodes if in_degree[nid] == 0]

        # ── 2a. Generate root node description ───────────────
        node_names = ", ".join(nodes[nid].name for nid in root_ids)
        
        num_attempts = 3
        for attempt in range(num_attempts):
            try:
                root_desc_msg = await self.llm.ainvoke(
                    [HumanMessage(content=config.PROMPT_ROOT_DESCRIPTION.format(
                        subject_id=subject_id, node_names=node_names
                    ))]
                )
                root_desc = root_desc_msg.content
                break  # success, exit loop
            except Exception as e:
                print(f"[Attempt {attempt + 1}/{num_attempts}] LLM error: {e}")
                if attempt == num_attempts - 1:
                    print("[Error] Failed to generate root description after multiple attempts.")
                    root_desc = "No description available due to LLM errors."
        root_desc = root_desc_msg.content
        tree_root = TreeNode(
            node_id="root",
            name=subject_id,
            description=root_desc,
            node_type="ROOT",
            level=0,
            chunk_ids=[],
        )

        # ── 2b. BFS to assign levels and record spanning-tree edges ────
        depth: dict[int, int] = {}
        tree_edge_set: set[tuple[int, int]] = set()
        queue = deque(root_ids)
        for rid in root_ids:
            depth[rid] = 1

        while queue:
            cur = queue.popleft()
            for nxt, _ in adj[cur]:
                if nxt not in depth:
                    depth[nxt] = depth[cur] + 1
                    tree_edge_set.add((cur, nxt))
                    queue.append(nxt)

        # ── 2c. Build tree nodes + generate DEFINE & TAG async (batched) ─

        BATCH_SIZE = 10

        # -- DEFINE edges: batch root_ids in groups of BATCH_SIZE --
        define_results: dict[int, str] = {}
        define_queue = list(root_ids)
        while define_queue:
            batch = define_queue[:BATCH_SIZE]
            define_queue = define_queue[BATCH_SIZE:]
            batch_coros = [
                self.llm.ainvoke(
                    [HumanMessage(content=config.PROMPT_DEFINE_DESCRIPTION.format(
                        subject_id=subject_id,
                        node_name=nodes[nid].name,
                        node_description=nodes[nid].description,
                    ))]
                )
                for nid in batch
            ]
            batch_results = await asyncio.gather(*batch_coros)
            for nid, res in zip(batch, batch_results):
                define_results[nid] = res.content

        # Non-tree edges (back-edges + same-level cross-edges) → TAG metadata
        # Use tree_edge_set so we catch ALL edges not in the spanning tree
        back_edges: dict[int, list[tuple[GraphEdge, GraphNode]]] = defaultdict(list)
        for e in edges:
            if (e.start_id, e.end_id) not in tree_edge_set:
                back_edges[e.start_id].append((e, nodes[e.end_id]))

        # -- TAG edges: batch in groups of BATCH_SIZE --
        tag_results: dict[tuple, str] = {}
        tag_items: list[tuple[tuple, ...]] = []
        for src_id, be_list in back_edges.items():
            for edge, target_node in be_list:
                tag_items.append((src_id, target_node, edge))

        tag_queue = list(tag_items)
        while tag_queue:
            batch = tag_queue[:BATCH_SIZE]
            tag_queue = tag_queue[BATCH_SIZE:]
            batch_coros = [
                self.llm.ainvoke(
                    [HumanMessage(content=config.PROMPT_TAG_DESCRIPTION.format(
                        rel_type=edge.rel_type,
                        source_name=nodes[src_id].name,
                        target_name=target_node.name,
                        rel_description=edge.description,
                        target_description=target_node.description,
                    ))]
                )
                for src_id, target_node, edge in batch
            ]
            batch_results = await asyncio.gather(*batch_coros)
            for (src_id, target_node, _edge), res in zip(batch, batch_results):
                tag_results[(src_id, target_node.identity)] = res.content
        # ── 2d. Assemble TreeNode list ────────────────────────
        tree_nodes: list[TreeNode] = [tree_root]
        tree_edges: list[tuple] = []  # (src_id, dst_id, rel_type, props)

        for nid, gnode in nodes.items():
            lv = depth.get(nid, 1)
            tags = []
            for edge, target_node in back_edges.get(nid, []):
                tag_text = tag_results.get((nid, target_node.identity), "")
                tags.append({
                    "rel_type": edge.rel_type,
                    "target_name": target_node.name,
                    "target_description": target_node.description,
                    "tag_description": tag_text,
                })

            tree_nodes.append(TreeNode(
                node_id=f"node_{nid}",
                name=gnode.name,
                description=gnode.description,
                node_type=gnode.node_type,
                level=lv,
                chunk_ids=gnode.chunk_ids,
                tags=tags,
            ))

        # Root → level-1 nodes (DEFINE edges)
        for nid in root_ids:
            tree_edges.append((
                "root", f"node_{nid}",
                config.TREE_EDGE_DEFINE,
                {"description": define_results.get(nid, "")},
            ))

        # Parent → child edges — only spanning-tree edges, preserve original rel_type
        visited: set[int] = set(root_ids)
        queue = deque(root_ids)
        while queue:
            cur = queue.popleft()
            for nxt, edge in adj[cur]:
                if (cur, nxt) in tree_edge_set:     # spanning-tree edge only
                    tree_edges.append((
                        f"node_{cur}", f"node_{nxt}",
                        edge.rel_type,
                        {"description": edge.description},
                    ))
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

        return tree_nodes, tree_edges

    # ── Step 3 – Save tree to Neo4j ───────────────────────────

    async def _save_tree(
        self,
        new_subject_id: str,
        tree_nodes: list[TreeNode],
        tree_edges: list[tuple],
    ) -> None:
        async with self._driver.session() as session:
            # Clear previous tree for this subject_id
            await session.run(
                "MATCH (n {subject_id: $sid}) DETACH DELETE n",
                sid=new_subject_id,
            )

            # Create nodes — tags stored as JSON string metadata on the node
            for tn in tree_nodes:
                label = config.TREE_ROOT_LABEL if tn.node_type == "ROOT" else config.TREE_NODE_LABEL
                await session.run(
                    f"""
                    CREATE (n:{label} {{
                        node_id: $node_id,
                        subject_id: $subject_id,
                        name: $name,
                        description: $description,
                        node_type: $node_type,
                        level: $level,
                        chunk_ids: $chunk_ids,
                        tags: $tags
                    }})
                    """,
                    node_id=tn.node_id,
                    subject_id=new_subject_id,
                    name=tn.name,
                    description=tn.description,
                    node_type=tn.node_type,
                    level=tn.level,
                    chunk_ids=tn.chunk_ids,
                    tags=json.dumps(tn.tags, ensure_ascii=False),
                )

            # Create tree edges (DEFINE + original rel_type spanning-tree edges)
            for src_id, dst_id, rel_type, props in tree_edges:
                await session.run(
                    f"""
                    MATCH (a {{node_id: $src, subject_id: $sid}})
                    MATCH (b {{node_id: $dst, subject_id: $sid}})
                    CREATE (a)-[:{rel_type} $props]->(b)
                    """,
                    src=src_id,
                    dst=dst_id,
                    sid=new_subject_id,
                    props=props,
                )

        print(f"[TreeBasedEngine] Saved tree under subject_id='{new_subject_id}'")