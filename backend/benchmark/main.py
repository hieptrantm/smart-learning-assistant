from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from benchmark.bootstrap import OUTPUT_DIR
from benchmark.ingestion_pipeline import BenchmarkIngestionPipeline
from benchmark.llm.together_llm import TogetherLLM
from benchmark.models import BenchmarkReport
from benchmark.strategy_runner import BenchmarkStrategyRunner, dump_report, summarize_delta
from benchmark.subject_repository import SubjectRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark tree-based vs knowledge-graph adaptive study planning")
    parser.add_argument("--subject-ids", type=int, nargs="+", required=True, help="Subject IDs to benchmark")
    parser.add_argument("--pdf-path", help="Optional PDF path for (re)ingestion before benchmarking")
    parser.add_argument("--raw-chunks-path", help="Optional raw chunks JSON for (re)ingestion before benchmarking")
    parser.add_argument("--recreate", action="store_true", help="Recreate Qdrant collections and clear subject graph before ingest")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip ingest/indexing and benchmark existing indexed subject data")
    return parser.parse_args()


async def benchmark_subject(
    subject_id: int,
    args: argparse.Namespace,
    llm_client: TogetherLLM,
) -> BenchmarkReport:
    repository = SubjectRepository()
    subject = repository.get_subject(subject_id)

    ingestion_result = None
    if not args.skip_ingest:
        ingestion_pipeline = BenchmarkIngestionPipeline(llm_client=llm_client)
        ingestion_result = await ingestion_pipeline.ingest_subject(
            subject,
            pdf_path=args.pdf_path,
            raw_chunks_path=args.raw_chunks_path,
            recreate=args.recreate,
        )

    session_weights = session_weights_from_subject(subject)
    runner = BenchmarkStrategyRunner(llm_client=llm_client)
    raw_graph = await runner.fetch_raw_graph(subject.subject_name)

    tree_result, kg_result = await asyncio.gather(
        runner.run_tree_strategy(subject, session_weights, raw_graph),
        runner.run_kg_strategy(session_weights, raw_graph),
    )
    return BenchmarkReport(
        subject=subject,
        ingestion=ingestion_result,
        tree_based=tree_result,
        knowledge_graph=kg_result,
        delta=summarize_delta(tree_result, kg_result),
    )


def session_weights_from_subject(subject) -> list[float]:
    weights: list[float] = []
    for day_slots in subject.free_slots.values():
        for slot in day_slots:
            if "-" in slot:
                start_text, end_text = slot.split("-", 1)
                start_hour, start_minute = parse_clock(start_text)
                end_hour, end_minute = parse_clock(end_text)
                duration = ((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)) / 60
                weights.append(max(duration, 0.5))
            else:
                weights.append(1.0)
    return weights or [1.0, 1.0, 1.0]


def parse_clock(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.strip().split(":", 1)
    return int(hour_text), int(minute_text)


async def main() -> None:
    args = parse_args()
    if not args.skip_ingest and not (args.pdf_path or args.raw_chunks_path):
        raise SystemExit("Provide --pdf-path or --raw-chunks-path, or pass --skip-ingest")

    llm_client = TogetherLLM()
    reports = []
    for subject_id in args.subject_ids:
        reports.append(await benchmark_subject(subject_id, args, llm_client))

    for report in reports:
        output_path = OUTPUT_DIR / f"subject_{report.subject.subject_id}_benchmark.json"
        dump_report(str(output_path), report.to_dict())
        print(f"Benchmark saved: {output_path}")
        print_summary(report)


def print_summary(report: BenchmarkReport) -> None:
    print(f"\nSubject {report.subject.subject_id} - {report.subject.subject_name}")
    print(f"  Tree-based      : {report.tree_based.total_ms:.2f} ms | prompt_tokens={report.tree_based.total_prompt_tokens} | context_retention={report.tree_based.context_retention_ratio:.3f}")
    print(f"  Knowledge graph : {report.knowledge_graph.total_ms:.2f} ms | prompt_tokens={report.knowledge_graph.total_prompt_tokens} | context_retention={report.knowledge_graph.context_retention_ratio:.3f}")
    print(f"  Delta           : time={report.delta['time_delta_ratio']:.3f} | tokens={report.delta['prompt_tokens_delta_ratio']:.3f} | context={report.delta['context_retention_delta_ratio']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())