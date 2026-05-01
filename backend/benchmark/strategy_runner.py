from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Iterable

from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from benchmark.bootstrap import configure_paths
from benchmark.llm.together_llm import TogetherLLM
from benchmark.models import SessionBenchmark, StrategyBenchmarkResult, SubjectDescriptor
from benchmark.token_estimator import TokenEstimator
from benchmark.vector_chunk_strategy import VectorChunkPlanner

import logging

configure_paths()

from app.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER  # type: ignore  # noqa: E402
from app.utils.graph_scheduler import GraphScheduler, graph_node_from_neo4j, graph_relationship_from_neo4j  # type: ignore  # noqa: E402
from app.utils.plan_generator import PlanGenerator  # type: ignore  # noqa: E402
from app.utils.scheduler import TreeScheduler, gen_desc_prompt, gen_qa_prompt, gen_title_prompt  # type: ignore  # noqa: E402
from rag_config import QDRANT_HOST, QDRANT_PORT  # type: ignore  # noqa: E402


logger = logging.getLogger(__name__)

PREREQUISITE_REL_TYPES = {"PREREQUISITE", "CAUSES", "APPLIES_TO"}
PART_OF_REL_TYPES = {"PART_OF"}
EXTENDED_KEY_REL_TYPES = {
    "DEFINES",
    "CAUSES",
    "RELATED_TO",
    "EXAMPLE_OF",
    "CONTRASTS",
    "APPLIES_TO",
    "DERIVED_FROM",
}
ALL_KEY_REL_TYPES = PREREQUISITE_REL_TYPES | PART_OF_REL_TYPES | EXTENDED_KEY_REL_TYPES


def _normalize_rel_type(rel_type: str) -> str:
    return str(rel_type or "").strip().replace(" ", "_").upper()


def _is_prerequisite(rel_type: str) -> bool:
    return _normalize_rel_type(rel_type) in PREREQUISITE_REL_TYPES


def _is_part_of(rel_type: str) -> bool:
    return _normalize_rel_type(rel_type) in PART_OF_REL_TYPES


def _is_key_relation(rel_type: str) -> bool:
    return _normalize_rel_type(rel_type) in ALL_KEY_REL_TYPES


def _jaccard_overlap(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


class RawGraphSnapshot:
    def __init__(self, nodes: dict[str, object], relationships: list[object]) -> None:
        self.nodes_by_name = nodes
        self.relationships = relationships
        self._identity_to_name = {node.identity: node.name for node in nodes.values()}
        self.edge_signatures = {
            (self._name(rel.start_identity), rel.rel_type, self._name(rel.end_identity))
            for rel in relationships
        }
        self.prerequisite_signatures = {
            signature for signature in self.edge_signatures if _is_prerequisite(signature[1])
        }
        self.part_of_signatures = {
            signature for signature in self.edge_signatures if _is_part_of(signature[1])
        }
        self.key_relation_signatures = {
            signature for signature in self.edge_signatures if _is_key_relation(signature[1])
        }
        self.subject_chunk_ids = {
            chunk_id
            for node in nodes.values()
            for chunk_id in node.chunk_ids
            if chunk_id
        }

    def _name(self, identity: int) -> str:
        return self._identity_to_name.get(identity, str(identity))


class BenchmarkStrategyRunner:
    def __init__(
        self,
        token_estimator: TokenEstimator | None = None,
        llm_client: TogetherLLM | None = None,
    ) -> None:
        self.token_estimator = token_estimator or TokenEstimator()
        self.llm_client = llm_client
        self._plan_generator = PlanGenerator(llm_client=llm_client)
        self._qdrant_client: QdrantClient | None = None

    @property
    def qdrant_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        return self._qdrant_client

    async def fetch_raw_graph(self, subject_name: str) -> RawGraphSnapshot:
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        nodes_by_name: dict[str, object] = {}
        relationships: list[object] = []
        seen_relationships: set[int] = set()

        query = """
        MATCH (n:Entity {subject_id: $sid})
        OPTIONAL MATCH (n)-[r]->(m:Entity {subject_id: $sid})
        RETURN n, r, m
        """

        try:
            async with driver.session() as session:
                result = await session.run(query, sid=subject_name)
                async for record in result:
                    node = record["n"]
                    node_info = graph_node_from_neo4j(node)
                    nodes_by_name[node_info.name] = node_info
                    rel = record["r"]
                    target = record["m"]
                    if rel is None or target is None or rel.id in seen_relationships:
                        continue
                    seen_relationships.add(rel.id)
                    target_info = graph_node_from_neo4j(target)
                    nodes_by_name[target_info.name] = target_info
                    relationships.append(graph_relationship_from_neo4j(rel))
        finally:
            await driver.close()

        return RawGraphSnapshot(nodes_by_name, relationships)

    async def run_tree_strategy(
        self,
        subject: SubjectDescriptor,
        session_weights: list[float],
        raw_graph: RawGraphSnapshot,
        checkpoint_node_id: str | None = None,
    ) -> StrategyBenchmarkResult:
        tree_subject_id = f"{subject.subject_name}_tree"
        logger.info(
            "[BenchmarkStrategyRunner] Running tree strategy for subject=%s with %s sessions",
            subject.subject_name,
            len(session_weights),
        )
        fetch_start = time.perf_counter()
        raw_paths = await self._plan_generator._fetch_tree_paths(tree_subject_id)
        logger.info(f"[BenchmarkStrategyRunner] Fetched {len(raw_paths)} tree paths for subject=%s", subject.subject_name)
        logger.info(f"[BenchmarkStrategyRunner] Sample tree path for subject=%s: %s", subject.subject_name, raw_paths[0] if raw_paths else "N/A")
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        if not raw_paths:
            logger.warning(
                "[BenchmarkStrategyRunner] No tree paths found for subject=%s; returning empty tree benchmark",
                subject.subject_name,
            )
            return self._empty_strategy_result(
                strategy_name="tree_based",
                fetch_ms=fetch_ms,
                session_weights=session_weights,
                raw_graph=raw_graph,
            )

        
        scheduler = TreeScheduler(raw_paths, llm_client=self.llm_client)
        logger.info(f"[BenchmarkStrategyRunner] Starting scheduling tree paths for subject=%s", subject.subject_name)
        schedule_start = time.perf_counter()
        schedule_results = await scheduler.schedule(session_weights, checkpoint_node_id)
        schedule_ms = (time.perf_counter() - schedule_start) * 1000
        logger.info(f"[BenchmarkStrategyRunner] Completed scheduling tree paths for subject=%s in %.2f ms", subject.subject_name, schedule_ms)
        return self._build_strategy_result(
            strategy_name="tree_based",
            fetch_ms=fetch_ms,
            schedule_ms=schedule_ms,
            session_weights=session_weights,
            schedule_results=schedule_results,
            raw_graph=raw_graph,
            tree_mode=True,
        )

    async def run_kg_strategy(
        self,
        session_weights: list[float],
        raw_graph: RawGraphSnapshot,
        checkpoint_node_id: str | None = None,
    ) -> StrategyBenchmarkResult:
        # Turn off for test
        # return self._build_strategy_result(
        #     strategy_name="knowledge_graph",
        #     fetch_ms=0.0,
        #     schedule_ms=0.0,
        #     session_weights=session_weights,
        #     schedule_results=[],
        #     raw_graph=raw_graph,
        #     tree_mode=False,
        # )
        
        logger.info(
            "[BenchmarkStrategyRunner] Running knowledge graph strategy with %s sessions",
            len(session_weights),
        )
        fetch_start = time.perf_counter()
        nodes = list(raw_graph.nodes_by_name.values())
        relationships = raw_graph.relationships
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        if not nodes:
            logger.warning(
                "[BenchmarkStrategyRunner] No knowledge-graph nodes found; returning empty graph benchmark"
            )
            return self._empty_strategy_result(
                strategy_name="knowledge_graph",
                fetch_ms=fetch_ms,
                session_weights=session_weights,
                raw_graph=raw_graph,
            )

        schedule_start = time.perf_counter()
        scheduler = GraphScheduler(nodes, relationships, llm_client=self.llm_client)
        schedule_results = await scheduler.schedule(session_weights, checkpoint_node_id)
        schedule_ms = (time.perf_counter() - schedule_start) * 1000
        return self._build_strategy_result(
            strategy_name="knowledge_graph",
            fetch_ms=fetch_ms,
            schedule_ms=schedule_ms,
            session_weights=session_weights,
            schedule_results=schedule_results,
            raw_graph=raw_graph,
            tree_mode=False,
        )

    async def run_vector_db_chunks_strategy(
        self,
        subject: SubjectDescriptor,
        session_weights: list[float],
        raw_graph: RawGraphSnapshot,
    ) -> StrategyBenchmarkResult:
        logger.info(
            "[BenchmarkStrategyRunner] Running vector-db chunks strategy for subject=%s with %s sessions",
            subject.subject_name,
            len(session_weights),
        )
        fetch_start = time.perf_counter()
        raw_chunks = self._fetch_raw_chunks(subject.subject_name)
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        if not raw_chunks:
            logger.warning(
                "[BenchmarkStrategyRunner] No raw chunks found in Qdrant for subject=%s",
                subject.subject_name,
            )
            return self._empty_strategy_result(
                strategy_name="vector_db_chunks",
                fetch_ms=fetch_ms,
                session_weights=session_weights,
                raw_graph=raw_graph,
            )

        schedule_start = time.perf_counter()
        planner = VectorChunkPlanner(
            self._group_nodes_by_chunk_id(raw_graph),
            raw_chunks,
            relationships=raw_graph.relationships,
            llm_client=self.llm_client,
        )
        schedule_results = await planner.schedule(session_weights)
        schedule_ms = (time.perf_counter() - schedule_start) * 1000
        return self._build_strategy_result(
            strategy_name="vector_db_chunks",
            fetch_ms=fetch_ms,
            schedule_ms=schedule_ms,
            session_weights=session_weights,
            schedule_results=schedule_results,
            raw_graph=raw_graph,
            tree_mode=False,
        )

    def _build_strategy_result(
        self,
        *,
        strategy_name: str,
        fetch_ms: float,
        schedule_ms: float,
        session_weights: list[float],
        schedule_results: Iterable,
        raw_graph: RawGraphSnapshot,
        tree_mode: bool,
    ) -> StrategyBenchmarkResult:
        session_benchmarks: list[SessionBenchmark] = []
        total_prompt_tokens = 0
        unique_primary_entities: set[str] = set()
        total_primary_entity_mentions = 0
        first_session_by_entity: dict[str, int] = {}
        activated_relations: set[tuple[str, str, str]] = set()
        activated_prerequisites: set[tuple[str, str, str]] = set()
        activated_part_of_relations: set[tuple[str, str, str]] = set()
        session_primary_entities: list[set[str]] = []

        for result in schedule_results:
            graph_entity_names = {node.name for node in result.nodes if node.name}
            # For vector strategy: fall back to chunk_ids as entity proxies when no graph nodes are mapped
            chunk_proxy_names = {cid for cid in getattr(result, "chunk_ids", []) if cid}
            primary_entities = graph_entity_names if graph_entity_names else chunk_proxy_names
            context_entities = {node.name for node in result.context_nodes}
            preserved_edges = self._collect_preserved_edges(result, tree_mode)
            activated_key_relations = preserved_edges & raw_graph.key_relation_signatures
            activated_prerequisite_relations = {
                signature for signature in activated_key_relations if _is_prerequisite(signature[1])
            }
            activated_part_of_session_relations = {
                signature for signature in activated_key_relations if _is_part_of(signature[1])
            }
            prompt_tokens = self._estimate_prompt_tokens(result.aggregate_text or "")
            total_prompt_tokens += prompt_tokens
            unique_primary_entities |= primary_entities
            total_primary_entity_mentions += len(primary_entities)
            activated_relations |= activated_key_relations
            activated_prerequisites |= activated_prerequisite_relations
            activated_part_of_relations |= activated_part_of_session_relations
            session_primary_entities.append(primary_entities)

            for entity_name in primary_entities:
                first_session_by_entity.setdefault(entity_name, result.session_index)

            session_benchmarks.append(
                SessionBenchmark(
                    session_index=result.session_index,
                    weight=result.weight,
                    primary_entity_count=len(primary_entities),
                    context_entity_count=len(context_entities),
                    activated_relation_count=len(activated_key_relations),
                    activated_prerequisite_count=len(activated_prerequisite_relations),
                    activated_part_of_count=len(activated_part_of_session_relations),
                    prompt_tokens=prompt_tokens,
                    aggregate_preview=(result.aggregate_text or "")[:240],
                )
            )

        total_ms = fetch_ms + schedule_ms
        prerequisite_evaluable = 0
        prerequisite_correct = 0
        for source_name, _, target_name in raw_graph.prerequisite_signatures:
            if source_name not in first_session_by_entity or target_name not in first_session_by_entity:
                continue
            prerequisite_evaluable += 1
            if first_session_by_entity[source_name] <= first_session_by_entity[target_name]:
                prerequisite_correct += 1

        prerequisite_violations = prerequisite_evaluable - prerequisite_correct
        adjacent_overlaps = [
            _jaccard_overlap(left, right)
            for left, right in zip(session_primary_entities, session_primary_entities[1:])
        ]
        unique_primary_entity_count = len(unique_primary_entities)
        return StrategyBenchmarkResult(
            strategy_name=strategy_name,
            fetch_ms=fetch_ms,
            schedule_ms=schedule_ms,
            total_ms=total_ms,
            session_count=len(session_benchmarks),
            session_weights=session_weights,
            total_prompt_tokens=total_prompt_tokens,
            avg_prompt_tokens=(total_prompt_tokens / len(session_benchmarks)) if session_benchmarks else 0.0,
            unique_primary_entities=unique_primary_entity_count,
            total_primary_entity_mentions=total_primary_entity_mentions,
            entity_redundancy_ratio=((total_primary_entity_mentions - unique_primary_entity_count) / total_primary_entity_mentions) if total_primary_entity_mentions else 0.0,
            avg_adjacent_entity_overlap=(sum(adjacent_overlaps) / len(adjacent_overlaps)) if adjacent_overlaps else 0.0,
            prerequisite_total=len(raw_graph.prerequisite_signatures),
            prerequisite_evaluable=prerequisite_evaluable,
            prerequisite_correct=prerequisite_correct,
            prerequisite_violations=prerequisite_violations,
            prerequisite_ordering_accuracy=(prerequisite_correct / prerequisite_evaluable) if prerequisite_evaluable else 1.0,
            key_relation_total=len(raw_graph.key_relation_signatures),
            activated_relation_total=len(activated_relations),
            relation_activation_rate=(len(activated_relations) / len(raw_graph.key_relation_signatures)) if raw_graph.key_relation_signatures else 1.0,
            prerequisite_activation_rate=(len(activated_prerequisites) / len(raw_graph.prerequisite_signatures)) if raw_graph.prerequisite_signatures else 1.0,
            part_of_activation_rate=(len(activated_part_of_relations) / len(raw_graph.part_of_signatures)) if raw_graph.part_of_signatures else 1.0,
            tokens_per_unique_entity=(total_prompt_tokens / unique_primary_entity_count) if unique_primary_entity_count else 0.0,
            sessions=session_benchmarks,
        )

    def _empty_strategy_result(
        self,
        *,
        strategy_name: str,
        fetch_ms: float,
        session_weights: list[float],
        raw_graph: RawGraphSnapshot,
    ) -> StrategyBenchmarkResult:
        return StrategyBenchmarkResult(
            strategy_name=strategy_name,
            fetch_ms=fetch_ms,
            schedule_ms=0.0,
            total_ms=fetch_ms,
            session_count=0,
            session_weights=session_weights,
            total_prompt_tokens=0,
            avg_prompt_tokens=0.0,
            unique_primary_entities=0,
            total_primary_entity_mentions=0,
            entity_redundancy_ratio=0.0,
            avg_adjacent_entity_overlap=0.0,
            prerequisite_total=len(raw_graph.prerequisite_signatures),
            prerequisite_evaluable=0,
            prerequisite_correct=0,
            prerequisite_violations=0,
            prerequisite_ordering_accuracy=1.0,
            key_relation_total=len(raw_graph.key_relation_signatures),
            activated_relation_total=0,
            relation_activation_rate=0.0,
            prerequisite_activation_rate=0.0,
            part_of_activation_rate=0.0,
            tokens_per_unique_entity=0.0,
            sessions=[],
        )

    def _estimate_prompt_tokens(self, aggregate_text: str) -> int:
        return (
            self.token_estimator.count(gen_title_prompt)
            + self.token_estimator.count(aggregate_text)
            + self.token_estimator.count(gen_desc_prompt)
            + self.token_estimator.count(gen_qa_prompt.format(nodes=aggregate_text))
        )

    @staticmethod
    def _collect_preserved_edges(result, tree_mode: bool) -> set[tuple[str, str, str]]:
        if tree_mode:
            node_names = {node.identity: node.name for node in result.nodes + result.context_nodes}
            preserved = {
                (node_names.get(rel.start_identity, str(rel.start_identity)), rel.rel_type, node_names.get(rel.end_identity, str(rel.end_identity)))
                for rel in result.relationships
            }
            for node in result.nodes:
                for tag in getattr(node, "tags", []):
                    preserved.add((node.name, tag.get("rel_type", ""), tag.get("target_name", "")))
            return preserved

        node_names = {node.identity: node.name for node in result.nodes + result.context_nodes}
        return {
            (node_names.get(rel.start_identity, str(rel.start_identity)), rel.rel_type, node_names.get(rel.end_identity, str(rel.end_identity)))
            for rel in result.relationships
        }

    def _fetch_raw_chunks(self, subject_name: str) -> list[dict[str, str]]:
        records, _ = self.qdrant_client.scroll(
            collection_name="raw_chunks",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="metadata.subject_id",
                        match=MatchValue(value=subject_name),
                    )
                ]
            ),
            with_payload=True,
            limit=512,
        )
        chunks: list[dict[str, str]] = []
        for record in records:
            payload = record.payload or {}
            metadata = payload.get("metadata", {}) or {}
            chunk_id = metadata.get("chunk_id") or payload.get("chunk_id")
            text = payload.get("page_content") or payload.get("text") or payload.get("document") or ""
            if not chunk_id or not text:
                continue
            chunks.append(
                {
                    "chunk_id": str(chunk_id),
                    "title": str(metadata.get("title") or chunk_id),
                    "text": str(text),
                }
            )
        chunks.sort(key=lambda item: item["chunk_id"])
        return chunks

    @staticmethod
    def _group_nodes_by_chunk_id(raw_graph: RawGraphSnapshot) -> dict[str, list[object]]:
        grouped: dict[str, list[object]] = defaultdict(list)
        for node in raw_graph.nodes_by_name.values():
            for chunk_id in getattr(node, "chunk_ids", []):
                if chunk_id:
                    grouped[chunk_id].append(node)
        return grouped


def _pair_delta(left_result: StrategyBenchmarkResult, right_result: StrategyBenchmarkResult) -> dict[str, float]:
    def pct_delta(tree_value: float, kg_value: float) -> float:
        if kg_value == 0:
            return 0.0
        return (tree_value - kg_value) / kg_value

    return {
        "time_delta_ratio": pct_delta(left_result.total_ms, right_result.total_ms),
        "prompt_tokens_delta_ratio": pct_delta(left_result.total_prompt_tokens, right_result.total_prompt_tokens),
        "prerequisite_ordering_accuracy_delta": left_result.prerequisite_ordering_accuracy - right_result.prerequisite_ordering_accuracy,
        "relation_activation_rate_delta": left_result.relation_activation_rate - right_result.relation_activation_rate,
        "entity_redundancy_ratio_delta": left_result.entity_redundancy_ratio - right_result.entity_redundancy_ratio,
        "tokens_per_unique_entity_delta_ratio": pct_delta(left_result.tokens_per_unique_entity, right_result.tokens_per_unique_entity),
    }


def summarize_delta(
    tree_result: StrategyBenchmarkResult,
    kg_result: StrategyBenchmarkResult,
    vector_result: StrategyBenchmarkResult,
) -> dict[str, dict[str, float]]:
    return {
        "tree_vs_knowledge_graph": _pair_delta(tree_result, kg_result),
        "tree_vs_vector_db_chunks": _pair_delta(tree_result, vector_result),
        "knowledge_graph_vs_vector_db_chunks": _pair_delta(kg_result, vector_result),
    }


def dump_report(path: str, report: dict) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, ensure_ascii=False, indent=2)
