import os
import json
import logging
from typing import Any, Dict, List

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_together import ChatTogether

from services.llm_service import LLMService
from rag_config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_URL,
    HIGHLEVEL_COLLECTION_NAME, LOWLEVEL_COLLECTION_NAME,
    RAW_CHUNKS_COLLECTION_NAME, EMBEDDING_MODEL,
    LLM_MODEL_ID, TOGETHER_API_KEY
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SearchEngine:
    """
    LightRAG Retrieval Engine.

    Flow:
      1. Extract keywords from query: low-level (specific terms) + high-level (broad themes)
      2. Qdrant vector search: find matching entities (low) and themes (high)
      3. Neo4j graph expansion: get 1-hop neighbors for full context
      4. Return compiled context (entities, themes, neighbors, descriptions)
    """

    def __init__(self, llm_api_key=None, llm_model=None):
        llm_client = ChatTogether(
            api_key=llm_api_key or TOGETHER_API_KEY,
            model=llm_model or LLM_MODEL_ID
        )
        self.llm = LLMService(
            client=llm_client
        )

        if QDRANT_URL:
            self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

        self._neo4j = None
        self._dense_emb = None

        self.low_collection = LOWLEVEL_COLLECTION_NAME
        self.high_collection = HIGHLEVEL_COLLECTION_NAME
        self.raw_collection = RAW_CHUNKS_COLLECTION_NAME

    @property
    def neo4j(self):
        if self._neo4j is None:
            self._neo4j = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return self._neo4j

    @property
    def dense_emb(self):
        if self._dense_emb is None:
            self._dense_emb = HuggingFaceBgeEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"trust_remote_code": True}
            )
        return self._dense_emb

    def close(self):
        if self._neo4j:
            self._neo4j.close()

    def _embed(self, text):
        return self.dense_emb.embed_query(text)

    # =========================================================================
    # Step 1: Extract keywords from query
    # =========================================================================

    def _extract_keywords(self, query):
        expanded = self.llm.expand_query(query)
        return {
            "low_level": expanded.get("main_concepts", [query]),
            "high_level": expanded.get("related_keywords", []),
            "type": expanded.get("question_type", "GENERAL")
        }

    # =========================================================================
    # Step 2: Qdrant vector search (named vector "dense")
    # =========================================================================

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        normalized = {}
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            normalized.update(metadata)

        for key, value in payload.items():
            if key != "metadata":
                normalized[key] = value

        return normalized

    def _search_qdrant(self, collection, query_text, top_k=5):
        embedding = self._embed(query_text)
        results = self.qdrant.search(
            collection_name=collection,
            query_vector=("dense", embedding),
            limit=top_k
        )
        return [
            {"score": h.score, "payload": self._normalize_payload(h.payload)}
            for h in results
        ]

    # =========================================================================
    # Step 3: Neo4j graph expansion (1-hop neighbors)
    # =========================================================================

    def _get_entity_details(self, entity_names):
        if not entity_names:
            return []
        with self.neo4j.session() as session:
            result = session.run(
                """UNWIND $names AS name
                MATCH (e:Entity {name: name})
                RETURN e.name AS name, e.type AS type,
                       e.description AS description,
                       e.chunk_ids AS chunk_ids""",
                names=entity_names
            )
            return [dict(record) for record in result]

    def _expand_graph(self, entity_names):
        if not entity_names:
            return []
        with self.neo4j.session() as session:
            result = session.run(
                """UNWIND $names AS name
                MATCH (e:Entity {name: name})-[r]-(neighbor:Entity)
                RETURN DISTINCT
                    e.name AS source,
                    type(r) AS relation,
                    r.description AS relation_desc,
                    neighbor.name AS neighbor_name,
                    neighbor.type AS neighbor_type,
                    neighbor.description AS neighbor_desc,
                    neighbor.chunk_ids AS neighbor_chunks""",
                names=entity_names
            )
            return [dict(record) for record in result]

    # =========================================================================
    # Deduplicate results
    # =========================================================================

    def _dedup_results(self, results, top_k):
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            payload = r.get("payload", {})
            key = (
                payload.get("entity_name")
                or payload.get("theme")
                or payload.get("chunk_id")
                or json.dumps(payload, sort_keys=True, ensure_ascii=False)
            )
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def _extract_chunk_ids(self, payload: Dict[str, Any]) -> List[str]:
        chunk_ids = []

        multi_chunk_ids = payload.get("chunk_ids", [])
        if isinstance(multi_chunk_ids, list):
            chunk_ids.extend(
                chunk_id for chunk_id in multi_chunk_ids if isinstance(chunk_id, str) and chunk_id
            )
        elif isinstance(multi_chunk_ids, str) and multi_chunk_ids:
            chunk_ids.append(multi_chunk_ids)

        single_chunk_id = payload.get("chunk_id")
        if isinstance(single_chunk_id, str) and single_chunk_id:
            chunk_ids.append(single_chunk_id)

        return list(dict.fromkeys(chunk_ids))

    def _aggregate_contexts_by_chunk(self, raw_results, low_results, high_results):
        aggregated_contexts = []

        for raw_result in raw_results:
            raw_payload = raw_result.get("payload", {})
            chunk_id = raw_payload.get("chunk_id")
            if not chunk_id:
                continue

            matched_low = []
            matched_high = []
            combined_contexts = []

            for low_result in low_results:
                if chunk_id in self._extract_chunk_ids(low_result.get("payload", {})):
                    matched_low.append(low_result)
                    combined_contexts.append({
                        "level": "low_level",
                        "data": low_result
                    })

            for high_result in high_results:
                if chunk_id in self._extract_chunk_ids(high_result.get("payload", {})):
                    matched_high.append(high_result)
                    combined_contexts.append({
                        "level": "high_level",
                        "data": high_result
                    })

            aggregated_contexts.append({
                "chunk_id": chunk_id,
                "raw_chunk": raw_result,
                "contexts": combined_contexts,
                "low_level": matched_low,
                "high_level": matched_high,
            })

        return aggregated_contexts

    # =========================================================================
    # Main search
    # =========================================================================

    def search(self, query, top_k=5, expand_graph=True):
        """
        Multi-level retrieval.

        Args:
            query: user question
            top_k: max results per level
            expand_graph: use Neo4j to get 1-hop neighbors

        Returns:
            dict with keywords, low_level, high_level, entity_details, graph_neighbors
        """
        logger.info(f"Search: {query}")

        # Step 1: Extract keywords
        keywords = self._extract_keywords(query)
        logger.info(f"Keywords - low: {keywords['low_level']}, high: {keywords['high_level']}")

        # Step 2: Qdrant search - raw chunks
        raw_results = []
        raw_queries = ([query] + keywords["low_level"] + keywords["high_level"])[:6]
        for kw in raw_queries:
            raw_results.extend(self._search_qdrant(self.raw_collection, kw, top_k))
        raw_results = self._dedup_results(raw_results, top_k)

        # Step 2: Qdrant search - low level (specific entities)
        low_results = []
        for kw in ([query] + keywords["low_level"])[:4]:
            low_results.extend(self._search_qdrant(self.low_collection, kw, top_k))
        low_results = self._dedup_results(low_results, top_k)

        # Step 2: Qdrant search - high level (broad themes)
        high_results = []
        for kw in ([query] + keywords["high_level"])[:4]:
            high_results.extend(self._search_qdrant(self.high_collection, kw, top_k))
        high_results = self._dedup_results(high_results, top_k)

        # Step 3: Graph expansion
        neighbors = []
        entity_details = []
        if expand_graph:
            entity_names = [
                r["payload"]["entity_name"]
                for r in low_results
                if r.get("payload", {}).get("entity_name")
            ]
            # Also include entities from high-level relation results
            for r in high_results:
                p = r.get("payload", {})
                for key in ("source_entity", "target_entity"):
                    if p.get(key):
                        entity_names.append(p[key])
            entity_names = list(set(entity_names))

            entity_details = self._get_entity_details(entity_names)
            neighbors = self._expand_graph(entity_names)

        aggregated_contexts = self._aggregate_contexts_by_chunk(
            raw_results=raw_results,
            low_results=low_results,
            high_results=high_results,
        )

        logger.info(
            f"Results - raw: {len(raw_results)}, low: {len(low_results)}, "
            f"high: {len(high_results)}, aggregated: {len(aggregated_contexts)}, "
            f"entities: {len(entity_details)}, neighbors: {len(neighbors)}"
        )

        return {
            "query": query,
            "keywords": keywords,
            "raw_level": raw_results,
            "low_level": low_results,
            "high_level": high_results,
            "aggregated_context": aggregated_contexts,
            "entity_details": entity_details,
            "graph_neighbors": neighbors
        }


if __name__ == "__main__":
    engine = SearchEngine()
    try:
        results = engine.search(
            "Noi dung chinh cua mon kinh te vi mo",
            top_k=5,
            expand_graph=True
        )
        print(json.dumps(results.get("aggregated_context", []), indent=2, ensure_ascii=False, default=str))
    finally:
        engine.close()
