from __future__ import annotations

import argparse
from dataclasses import dataclass

import psycopg2
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/authdb"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "testtest")
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTIONS = ["raw_chunks", "low-level-retrieval", "high-level-retrieval"]


@dataclass
class SubjectSeed:
    user_id: int
    name: str
    target_grade: float
    end_date: str
    slots: list[tuple[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset one benchmark subject across DB, Neo4j and Qdrant")
    parser.add_argument("--subject-id", type=int, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--target-grade", type=float, default=7.0)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--slots", nargs="+", required=True, help="day=time, for example tue=11:00 fri=09:00")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed = SubjectSeed(
        user_id=args.user_id,
        name=args.name,
        target_grade=args.target_grade,
        end_date=args.end_date,
        slots=[tuple(item.split("=", 1)) for item in args.slots],
    )

    new_subject_id = reset_postgres(args.subject_id, seed)
    reset_neo4j(seed.name)
    reset_qdrant(seed.name)
    print({"new_subject_id": new_subject_id, "subject_name": seed.name})


def reset_postgres(old_subject_id: int, seed: SubjectSeed) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("delete from study_subjects where id = %s", (old_subject_id,))
            cursor.execute(
                """
                insert into study_subjects (
                    user_id, name, target_grade, end_date, status, ingest_status, plan_status
                ) values (%s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    seed.user_id,
                    seed.name,
                    seed.target_grade,
                    seed.end_date,
                    "active",
                    "pending",
                    "pending",
                ),
            )
            new_subject_id = cursor.fetchone()[0]
            cursor.executemany(
                "insert into subject_free_slots (subject_id, day_of_week, time_slot) values (%s, %s, %s)",
                [(new_subject_id, day, slot) for day, slot in seed.slots],
            )
        conn.commit()
        return new_subject_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_neo4j(subject_name: str) -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with driver.session() as session:
            session.run(
                "MATCH (n) WHERE n.subject_id = $sid OR n.subject_id = $tree_sid DETACH DELETE n",
                sid=subject_name,
                tree_sid=f"{subject_name}_tree",
            ).consume()
    finally:
        driver.close()


def reset_qdrant(subject_name: str) -> None:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)
    filters = [
        Filter(must=[FieldCondition(key="metadata.subject_id", match=MatchValue(value=subject_name))]),
        Filter(must=[FieldCondition(key="subject_id", match=MatchValue(value=subject_name))]),
    ]
    for collection_name in COLLECTIONS:
        for filt in filters:
            client.delete(
                collection_name=collection_name,
                points_selector=FilterSelector(filter=filt),
                wait=True,
            )


if __name__ == "__main__":
    main()