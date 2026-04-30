from __future__ import annotations

import json
import os
import time
from pathlib import Path

from benchmark.bootstrap import OUTPUT_DIR, configure_paths
from benchmark.config import BENCHMARK_LLM_MODEL, BENCHMARK_TOGETHER_API_KEY
from benchmark.llm.together_llm import TogetherLLM
from benchmark.models import IngestionBenchmarkResult, SubjectDescriptor
from benchmark.llm_service import BenchmarkLLMService

configure_paths()

from indexing.engine import IndexingEngine  # type: ignore  # noqa: E402
from ingestor.engine import ChunkingEngine  # type: ignore  # noqa: E402
from services.vlm_service import VLMService  # type: ignore  # noqa: E402


class BenchmarkIngestionPipeline:
    def __init__(self, llm_client: TogetherLLM | None = None) -> None:
        self._chunking_engine: ChunkingEngine | None = None
        self._indexing_engine: IndexingEngine | None = None
        self._llm_client = llm_client

    @property
    def chunking_engine(self) -> ChunkingEngine:
        if self._chunking_engine is None:
            self._chunking_engine = ChunkingEngine(vlm_service=VLMService())
        return self._chunking_engine

    @property
    def indexing_engine(self) -> IndexingEngine:
        if self._indexing_engine is None:
            os.environ.setdefault("TOGETHER_API_KEY", BENCHMARK_TOGETHER_API_KEY)
            os.environ.setdefault("LLM_API_KEY", BENCHMARK_TOGETHER_API_KEY)
            os.environ.setdefault("LLM_MODEL_ID", BENCHMARK_LLM_MODEL)
            self._indexing_engine = IndexingEngine(
                llm=BenchmarkLLMService(client=self._llm_client or TogetherLLM())
            )
        return self._indexing_engine

    async def ingest_subject(
        self,
        subject: SubjectDescriptor,
        *,
        pdf_path: str | None = None,
        raw_chunks_path: str | None = None,
        recreate: bool = False,
    ) -> IngestionBenchmarkResult:
        if not pdf_path and not raw_chunks_path:
            raise ValueError("Either pdf_path or raw_chunks_path must be provided for ingestion")

        start = time.perf_counter()
        if raw_chunks_path:
            source = "raw_chunks"
            chunks = self._load_raw_chunks(raw_chunks_path)
        else:
            source = "pdf"
            ingest_result = self.chunking_engine.run_pipeline(pdf_path, subject.subject_name)
            chunks = ingest_result.chunks

        kg_path = OUTPUT_DIR / f"{subject.subject_name}_knowledge_graph.json"
        stats = await self.indexing_engine.ingest(
            chunks=chunks,
            subject_id=subject.subject_name,
            save_to_neo4j=True,
            save_kg_json=str(kg_path),
            recreate=recreate,
        )
        duration_ms = (time.perf_counter() - start) * 1000
        return IngestionBenchmarkResult(
            duration_ms=duration_ms,
            chunks=stats.get("chunks", 0),
            entities_raw=stats.get("entities_raw", 0),
            entities_profiled=stats.get("entities_profiled", 0),
            relations=stats.get("relations", 0),
            high_level_keys=stats.get("high_level_keys", 0),
            source=source,
        )

    @staticmethod
    def _load_raw_chunks(raw_chunks_path: str) -> list[dict]:
        data = json.loads(Path(raw_chunks_path).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "chunks" in data:
            return data["chunks"]
        raise ValueError(f"Unsupported raw chunks payload in {raw_chunks_path}")
