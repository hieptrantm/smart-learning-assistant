from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SubjectDescriptor:
    subject_id: int
    subject_name: str
    target_grade: float | None
    start_date: str | None
    end_date: str | None
    free_slots: dict[str, list[str]]


@dataclass
class BenchmarkJob:
    subject: SubjectDescriptor
    pdf_path: str | None = None
    raw_chunks_path: str | None = None
    session_weights: list[float] | None = None


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
    primary_entity_count: int
    context_entity_count: int
    activated_relation_count: int
    activated_prerequisite_count: int
    activated_part_of_count: int
    prompt_tokens: int
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
    unique_primary_entities: int
    total_primary_entity_mentions: int
    entity_redundancy_ratio: float
    avg_adjacent_entity_overlap: float
    prerequisite_total: int
    prerequisite_evaluable: int
    prerequisite_correct: int
    prerequisite_violations: int
    prerequisite_ordering_accuracy: float
    key_relation_total: int
    activated_relation_total: int
    relation_activation_rate: float
    prerequisite_activation_rate: float
    part_of_activation_rate: float
    tokens_per_unique_entity: float
    sessions: list[SessionBenchmark] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    subject: SubjectDescriptor
    ingestion: IngestionBenchmarkResult | None
    tree_based: StrategyBenchmarkResult
    knowledge_graph: StrategyBenchmarkResult
    vector_db_chunks: StrategyBenchmarkResult
    delta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
