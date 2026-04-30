from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Iterable

from neo4j import AsyncGraphDatabase

from benchmark.bootstrap import configure_paths
from benchmark.llm.together_llm import TogetherLLM
from benchmark.models import SessionBenchmark, StrategyBenchmarkResult, SubjectDescriptor
from benchmark.token_estimator import TokenEstimator

import logging

configure_paths()

from app.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER  # type: ignore  # noqa: E402
from app.utils.graph_scheduler import GraphScheduler, graph_node_from_neo4j, graph_relationship_from_neo4j  # type: ignore  # noqa: E402
from app.utils.plan_generator import PlanGenerator  # type: ignore  # noqa: E402
from app.utils.scheduler import TreeScheduler, gen_desc_prompt, gen_qa_prompt, gen_title_prompt  # type: ignore  # noqa: E402


logger = logging.getLogger(__name__)


class RawGraphSnapshot:
    def __init__(self, nodes: dict[str, object], relationships: list[object]) -> None:
        self.nodes_by_name = nodes
        self.relationships = relationships
        self.edge_signatures = {
            (self._name(rel.start_identity), rel.rel_type, self._name(rel.end_identity))
            for rel in relationships
        }
        self.subject_chunk_ids = {
            chunk_id
            for node in nodes.values()
            for chunk_id in node.chunk_ids
            if chunk_id
        }

    def relevant_edges(self, session_node_names: set[str], known_node_names: set[str]) -> set[tuple[str, str, str]]:
        all_known = session_node_names | known_node_names
        signatures: set[tuple[str, str, str]] = set()
        for rel in self.relationships:
            start_name = self._name(rel.start_identity)
            end_name = self._name(rel.end_identity)
            touches_session = start_name in session_node_names or end_name in session_node_names
            both_known = start_name in all_known and end_name in all_known
            if touches_session and both_known:
                signatures.add((start_name, rel.rel_type, end_name))
        return signatures

    def _name(self, identity: int) -> str:
        for node in self.nodes_by_name.values():
            if node.identity == identity:
                return node.name
        return str(identity)


class BenchmarkStrategyRunner:
    def __init__(
        self,
        token_estimator: TokenEstimator | None = None,
        llm_client: TogetherLLM | None = None,
    ) -> None:
        self.token_estimator = token_estimator or TokenEstimator()
        self.llm_client = llm_client
        self._plan_generator = PlanGenerator(llm_client=llm_client)

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
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

        schedule_start = time.perf_counter()
        scheduler = TreeScheduler(raw_paths, llm_client=self.llm_client)
        schedule_results = await scheduler.schedule(session_weights, checkpoint_node_id)
        schedule_ms = (time.perf_counter() - schedule_start) * 1000
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
        logger.info(
            "[BenchmarkStrategyRunner] Running knowledge graph strategy with %s sessions",
            len(session_weights),
        )
        fetch_start = time.perf_counter()
        nodes = list(raw_graph.nodes_by_name.values())
        relationships = raw_graph.relationships
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

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
        known_node_names: set[str] = set()
        total_prompt_tokens = 0
        total_relevant_edges = 0
        total_preserved_edges = 0
        payload_chunk_ids: set[str] = set()
        node_count = 0
        relationship_count = 0

        for result in schedule_results:
            session_node_names = {node.name for node in result.nodes}
            payload_chunk_ids |= {
                chunk_id
                for node in list(result.nodes) + list(result.context_nodes)
                for chunk_id in getattr(node, "chunk_ids", [])
                if chunk_id
            }
            relevant_edges = raw_graph.relevant_edges(session_node_names, known_node_names)
            preserved_edges = self._collect_preserved_edges(result, tree_mode)
            prompt_tokens = self._estimate_prompt_tokens(result.aggregate_text)
            total_prompt_tokens += prompt_tokens
            total_relevant_edges += len(relevant_edges)
            total_preserved_edges += len(relevant_edges & preserved_edges)
            node_count += len(result.nodes)
            relationship_count += len(result.relationships)
            session_benchmarks.append(
                SessionBenchmark(
                    session_index=result.session_index,
                    weight=result.weight,
                    node_count=len(result.nodes),
                    relationship_count=len(result.relationships),
                    context_node_count=len(result.context_nodes),
                    prompt_tokens=prompt_tokens,
                    relevant_context_edges=len(relevant_edges),
                    preserved_context_edges=len(relevant_edges & preserved_edges),
                    context_retention_ratio=(len(relevant_edges & preserved_edges) / len(relevant_edges)) if relevant_edges else 1.0,
                    payload_chunk_count=len({chunk_id for node in list(result.nodes) + list(result.context_nodes) for chunk_id in getattr(node, "chunk_ids", []) if chunk_id}),
                    aggregate_preview=result.aggregate_text[:240],
                )
            )
            known_node_names |= session_node_names

        total_ms = fetch_ms + schedule_ms
        subject_chunk_count = len(raw_graph.subject_chunk_ids)
        payload_chunk_count = len(payload_chunk_ids)
        return StrategyBenchmarkResult(
            strategy_name=strategy_name,
            fetch_ms=fetch_ms,
            schedule_ms=schedule_ms,
            total_ms=total_ms,
            session_count=len(session_benchmarks),
            session_weights=session_weights,
            total_prompt_tokens=total_prompt_tokens,
            avg_prompt_tokens=(total_prompt_tokens / len(session_benchmarks)) if session_benchmarks else 0.0,
            relevant_context_edges=total_relevant_edges,
            preserved_context_edges=total_preserved_edges,
            context_retention_ratio=(total_preserved_edges / total_relevant_edges) if total_relevant_edges else 1.0,
            subject_chunk_count=subject_chunk_count,
            payload_chunk_count=payload_chunk_count,
            payload_chunk_ratio=(payload_chunk_count / subject_chunk_count) if subject_chunk_count else 0.0,
            node_count=node_count,
            relationship_count=relationship_count,
            sessions=session_benchmarks,
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


def summarize_delta(tree_result: StrategyBenchmarkResult, kg_result: StrategyBenchmarkResult) -> dict[str, float]:
    def pct_delta(tree_value: float, kg_value: float) -> float:
        if kg_value == 0:
            return 0.0
        return (tree_value - kg_value) / kg_value

    return {
        "time_delta_ratio": pct_delta(tree_result.total_ms, kg_result.total_ms),
        "prompt_tokens_delta_ratio": pct_delta(tree_result.total_prompt_tokens, kg_result.total_prompt_tokens),
        "context_retention_delta_ratio": tree_result.context_retention_ratio - kg_result.context_retention_ratio,
        "payload_chunk_ratio_delta": tree_result.payload_chunk_ratio - kg_result.payload_chunk_ratio,
    }


def dump_report(path: str, report: dict) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, ensure_ascii=False, indent=2)
