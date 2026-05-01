from __future__ import annotations

import argparse

import psycopg2
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams
from qdrant_client.http import models as qdrant_models

from benchmark.bootstrap import configure_paths
from benchmark.config import DATABASE_URL, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, QDRANT_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_URL


configure_paths()

from rag_config import EMBEDDING_DIMENSION, HIGHLEVEL_COLLECTION_NAME, LOWLEVEL_COLLECTION_NAME, RAW_CHUNKS_COLLECTION_NAME  # type: ignore  # noqa: E402


COLLECTION_SPECS = {
    RAW_CHUNKS_COLLECTION_NAME: EMBEDDING_DIMENSION,
    LOWLEVEL_COLLECTION_NAME: EMBEDDING_DIMENSION,
    HIGHLEVEL_COLLECTION_NAME: EMBEDDING_DIMENSION,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete all subject data from Postgres, Neo4j, and Qdrant")
    parser.add_argument("--yes", action="store_true", help="Actually perform the destructive reset")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.yes:
        raise SystemExit("Refusing to run without --yes")

    postgres_summary = reset_postgres()
    neo4j_summary = reset_neo4j()
    qdrant_summary = reset_qdrant()
    print(
        {
            "postgres": postgres_summary,
            "neo4j": neo4j_summary,
            "qdrant": qdrant_summary,
        }
    )


def reset_postgres() -> dict[str, int]:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("select count(*) from study_subjects")
            subject_count = cursor.fetchone()[0]
            cursor.execute("delete from study_subjects")
        conn.commit()
        return {"deleted_subjects": subject_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_neo4j() -> dict[str, int]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            count_result = session.run(
                "MATCH (n) WHERE n.subject_id IS NOT NULL RETURN count(n) AS count"
            ).single()
            node_count = int(count_result["count"]) if count_result is not None else 0
            session.run("MATCH (n) WHERE n.subject_id IS NOT NULL DETACH DELETE n").consume()
        return {"deleted_nodes": node_count}
    finally:
        driver.close()


def reset_qdrant() -> dict[str, int]:
    client = _create_qdrant_client()
    recreated = 0
    for collection_name, dimension in COLLECTION_SPECS.items():
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(size=dimension, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=qdrant_models.SparseIndexParams(on_disk=False)
                )
            },
        )
        recreated += 1
    return {"recreated_collections": recreated}


def _create_qdrant_client() -> QdrantClient:
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)


if __name__ == "__main__":
    main()