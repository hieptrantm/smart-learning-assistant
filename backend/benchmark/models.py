from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SubjectDescriptor:
    subject_id: int
    subject_name: str
    target_grade: float | None
    end_date: str | None
    free_slots: dict[str, list[str]]


@dataclass
class IngestionBenchmarkResult:
    duration_ms: float
    chunks: int
    entities_raw: int
    entities_profiled: int
    relations: int
    high_level_keys: int
    source: str


@dataclass
class SessionBenchmark:
    session_index: int
    weight: float
    node_count: int
    relationship_count: int
    context_node_count: int
    prompt_tokens: int
    relevant_context_edges: int
    preserved_context_edges: int
    context_retention_ratio: float
    payload_chunk_count: int
    aggregate_preview: str


@dataclass
class StrategyBenchmarkResult:
    strategy_name: str
    fetch_ms: float
    schedule_ms: float
    total_ms: float
    session_count: int
    session_weights: list[float]
    total_prompt_tokens: int
    avg_prompt_tokens: float
    relevant_context_edges: int
    preserved_context_edges: int
    context_retention_ratio: float
    subject_chunk_count: int
    payload_chunk_count: int
    payload_chunk_ratio: float
    node_count: int
    relationship_count: int
    sessions: list[SessionBenchmark] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    subject: SubjectDescriptor
    ingestion: IngestionBenchmarkResult | None
    tree_based: StrategyBenchmarkResult
    knowledge_graph: StrategyBenchmarkResult
    delta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
