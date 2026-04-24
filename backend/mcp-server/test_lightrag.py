"""
Test LightRAG dual-level retrieval pipeline.
Requires: Neo4j running, Qdrant running, indexed data for subject.
"""
import asyncio
import logging
from tools.lightrag_retrieval import LightRAGRetrieval

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SUBJECT_ID = "cổ tích"
SUBJECT_ID = 4
TEST_QUERIES = [
    # Low-level: specific entity query
    # "Ai là nhân vật chính trong câu chuyện này?",
    # High-level: broad theme query
    # "Người bà có liên quan gì đến nhân vật chính?
    "minh",
]

from llm.together_llm import TogetherLLM
from config import TOGETHER_API_KEY, LLM_MODEL_ID
from vectordb.engine import VectorDBEngine
from graph_db.engine import GraphDBEngine

llm_client = TogetherLLM(
    together_api_key=TOGETHER_API_KEY,
    model_name=LLM_MODEL_ID
)
vectordb_engine = VectorDBEngine()
graphdb_engine = GraphDBEngine()

async def test_full_retrieval():
    
    retrieval = LightRAGRetrieval(
        llm_client=llm_client,
        vectordb_engine=vectordb_engine,
        graphdb_engine=graphdb_engine
    )

    for query in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")

        result = await retrieval.retrieve(
            query=query,
            subject_id=SUBJECT_ID
        )

        print(f"\n--- Context (first 1000 chars) ---")
        print(result["context"])

        print(f"\n--- Stats ---")
        print(f"  Low-level docs:   {len(result['low_level_docs'])}")
        print(f"  High-level docs:  {len(result['high_level_docs'])}")
        print(f"  Graph entities:   {len(result['graph_expansion']['entities'])}")
        print(f"  Graph relations:  {len(result['graph_expansion']['relations'])}")
        print(f"  Source chunk IDs: {len(result['chunk_ids'])}")

    retrieval.graphdb.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test_full_retrieval())
