from __future__ import annotations

import argparse
import asyncio

from benchmark.batch_runtime import BenchmarkRuntime
from benchmark.bootstrap import OUTPUT_DIR
from benchmark.models import BenchmarkJob, BenchmarkReport, SubjectDescriptor
from benchmark.strategy_runner import BenchmarkStrategyRunner, dump_report, summarize_delta
from benchmark.subject_repository import SubjectRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark tree-based vs knowledge-graph adaptive study planning")
    subject_source = parser.add_mutually_exclusive_group(required=True)
    subject_source.add_argument("--subject-ids", type=int, nargs="+", help="Existing subject IDs to benchmark")
    subject_source.add_argument("--subject-name", help="Benchmark a new ad-hoc subject without loading metadata from Postgres")
    subject_source.add_argument("--subjects-json", help="Benchmark many subjects from a JSON manifest with id, name, and pdf url/path")
    parser.add_argument("--subject-id", type=int, default=0, help="Logical ID for ad-hoc subject runs; used in output filenames")
    parser.add_argument("--target-grade", type=float, help="Optional target grade for ad-hoc subject runs")
    parser.add_argument("--start-date", help="Optional ISO start date for ad-hoc subject runs")
    parser.add_argument("--end-date", help="Optional ISO date for ad-hoc subject runs")
    parser.add_argument("--slots", nargs="+", help="Ad-hoc free slots in the form day=09:00-11:00 or day=09:00")
    parser.add_argument("--session-count", type=int, help="Optional fixed number of sessions to benchmark")
    parser.add_argument("--session-weight", type=float, default=1.0, help="Weight to use for each fixed session when --session-count is set")
    parser.add_argument("--pdf-path", help="Optional PDF path for (re)ingestion before benchmarking")
    parser.add_argument("--raw-chunks-path", help="Optional raw chunks JSON for (re)ingestion before benchmarking")
    parser.add_argument("--recreate", action="store_true", help="Recreate Qdrant collections and clear subject graph before ingest")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip ingest/indexing and benchmark existing indexed subject data")
    args = parser.parse_args()
    if args.subject_name and not args.slots:
        parser.error("--slots is required when using --subject-name")
    return args


def build_ad_hoc_subject(args: argparse.Namespace) -> SubjectDescriptor:
    return SubjectDescriptor(
        subject_id=args.subject_id,
        subject_name=args.subject_name,
        target_grade=args.target_grade,
        start_date=args.start_date,
        end_date=args.end_date,
        free_slots=parse_slots(args.slots or []),
    )


def parse_slots(slot_args: list[str]) -> dict[str, list[str]]:
    free_slots: dict[str, list[str]] = {}
    for slot_arg in slot_args:
        if "=" not in slot_arg:
            raise SystemExit(f"Invalid slot '{slot_arg}'. Expected day=09:00 or day=09:00-11:00")
        day, slot = slot_arg.split("=", 1)
        day = day.strip().lower()
        slot = slot.strip()
        if not day or not slot:
            raise SystemExit(f"Invalid slot '{slot_arg}'. Expected day=09:00 or day=09:00-11:00")
        free_slots.setdefault(day, []).append(slot)
    return {key: sorted(value) for key, value in free_slots.items()}


def resolve_subjects(args: argparse.Namespace) -> list[SubjectDescriptor]:
    if args.subject_name:
        return [build_ad_hoc_subject(args)]

    repository = SubjectRepository()
    return [repository.get_subject(subject_id) for subject_id in args.subject_ids]


async def resolve_jobs(args: argparse.Namespace, runtime: BenchmarkRuntime) -> list[BenchmarkJob]:
    if args.subjects_json:
        return await runtime.load_jobs_from_manifest(args.subjects_json)

    fixed_session_weights = None
    if args.session_count is not None:
        if args.session_count <= 0:
            raise SystemExit("--session-count must be a positive integer")
        if args.session_weight <= 0:
            raise SystemExit("--session-weight must be a positive number")
        fixed_session_weights = [args.session_weight] * args.session_count

    return [
        BenchmarkJob(
            subject=subject,
            pdf_path=args.pdf_path,
            raw_chunks_path=args.raw_chunks_path,
            session_weights=fixed_session_weights,
        )
        for subject in resolve_subjects(args)
    ]


async def benchmark_subject(
    job: BenchmarkJob,
    args: argparse.Namespace,
    runtime: BenchmarkRuntime,
) -> BenchmarkReport:
    subject = job.subject

    ingestion_result = None
    if not args.skip_ingest:
        ingestion_result = await runtime.ingestion_pipeline.ingest_subject(
            subject,
            pdf_path=job.pdf_path,
            raw_chunks_path=job.raw_chunks_path,
            recreate=args.recreate,
        )

    session_weights = job.session_weights or session_weights_from_subject(subject)
    raw_graph = await runtime.strategy_runner.fetch_raw_graph(subject.subject_name)

    tree_result, kg_result, vector_result = await asyncio.gather(
        runtime.strategy_runner.run_tree_strategy(subject, session_weights, raw_graph),
        runtime.strategy_runner.run_kg_strategy(session_weights, raw_graph),
        runtime.strategy_runner.run_vector_db_chunks_strategy(subject, session_weights, raw_graph),
    )
    
    # tree_result = await runtime.strategy_runner.run_tree_strategy(subject, session_weights, raw_graph)
    
    return BenchmarkReport(
        subject=subject,
        ingestion=ingestion_result,
        tree_based=tree_result,
        knowledge_graph=kg_result,
        vector_db_chunks=vector_result,
        delta=summarize_delta(tree_result, kg_result, vector_result),
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
    if not args.skip_ingest and not (args.pdf_path or args.raw_chunks_path or args.subjects_json):
        raise SystemExit("Provide --pdf-path or --raw-chunks-path, or pass --skip-ingest")

    runtime = BenchmarkRuntime()
    try:
        jobs = await resolve_jobs(args, runtime)
        await runtime.warmup(include_ingestion=not args.skip_ingest)

        reports = []
        for job in jobs:
            reports.append(await benchmark_subject(job, args, runtime))

    finally:
        await runtime.close()

    for report in reports:
        output_path = OUTPUT_DIR / f"subject_{report.subject.subject_id}_benchmark.json"
        dump_report(str(output_path), report.to_dict())
        print(f"Benchmark saved: {output_path}", flush=True)
        print_summary(report)


def print_summary(report: BenchmarkReport) -> None:
    tree_vs_vector = report.delta["tree_vs_vector_db_chunks"]
    kg_vs_vector = report.delta["knowledge_graph_vs_vector_db_chunks"]
    print(f"\nSubject {report.subject.subject_id} - {report.subject.subject_name}", flush=True)
    print(
        "  Tree-based      : "
        f"{report.tree_based.total_ms:.2f} ms | "
        f""
        f"prereq_order={report.tree_based.prerequisite_ordering_accuracy:.3f} | "
        f"rel_activation={report.tree_based.relation_activation_rate:.3f} | "
        f"entity_redundancy={report.tree_based.entity_redundancy_ratio:.3f} | "
        f"tokens_per_entity={report.tree_based.tokens_per_unique_entity:.1f}"
    , flush=True)
    print(
        "  Knowledge graph : "
        f"{report.knowledge_graph.total_ms:.2f} ms | "
        f"prereq_order={report.knowledge_graph.prerequisite_ordering_accuracy:.3f} | "
        f"rel_activation={report.knowledge_graph.relation_activation_rate:.3f} | "
        f"entity_redundancy={report.knowledge_graph.entity_redundancy_ratio:.3f} | "
        f"tokens_per_entity={report.knowledge_graph.tokens_per_unique_entity:.1f}"
    , flush=True)
    print(
        "  VectorDB chunks : "
        f"{report.vector_db_chunks.total_ms:.2f} ms | "
        f"prereq_order={report.vector_db_chunks.prerequisite_ordering_accuracy:.3f} | "
        f"rel_activation={report.vector_db_chunks.relation_activation_rate:.3f} | "
        f"entity_redundancy={report.vector_db_chunks.entity_redundancy_ratio:.3f} | "
        f"tokens_per_entity={report.vector_db_chunks.tokens_per_unique_entity:.1f}"
    , flush=True)
    print(
        "  Tree vs Vector  : "
        f"time={tree_vs_vector['time_delta_ratio']:.3f} | "
        f"prereq={tree_vs_vector['prerequisite_ordering_accuracy_delta']:.3f} | "
        f"rel={tree_vs_vector['relation_activation_rate_delta']:.3f} | "
        f"redundancy={tree_vs_vector['entity_redundancy_ratio_delta']:.3f} | "
        f"token_eff={tree_vs_vector['tokens_per_unique_entity_delta_ratio']:.3f}"
    , flush=True)
    print(
        "  KG vs Vector    : "
        f"time={kg_vs_vector['time_delta_ratio']:.3f} | "
        f"prereq={kg_vs_vector['prerequisite_ordering_accuracy_delta']:.3f} | "
        f"rel={kg_vs_vector['relation_activation_rate_delta']:.3f} | "
        f"redundancy={kg_vs_vector['entity_redundancy_ratio_delta']:.3f} | "
        f"token_eff={kg_vs_vector['tokens_per_unique_entity_delta_ratio']:.3f}"
    , flush=True)


if __name__ == "__main__":
    asyncio.run(main())