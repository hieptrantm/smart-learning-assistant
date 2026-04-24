import logging, asyncio, json
from pydantic import Field
from typing import Annotated, List, Dict, Any, Optional, Tuple

from llm.base import BaseLLM
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_qdrant import RetrievalMode

from vectordb.engine import VectorDBEngine
from graph_db.engine import GraphDBEngine
from db.db_utils import get_subject_name_by_id
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYWORD_PROMPT = """Extract search keywords from the query below.
Return ONLY valid JSON: {{"local_keywords": ["..."], "global_keywords": ["..."]}}
- local_keywords: specific entity names, terms, proper nouns
- global_keywords: broad themes, concepts, abstract topics

Query: {query}"""


class LightRAGRetrieval:
    """
    LightRAG dual-level retrieval: low-level (entities) + high-level (relations)
    
    Flow:
      1. Extract local + global keywords (LLM)
      2. Low-level: vector search entity collection → graph one-hop
      3. High-level: vector search relation collection → graph one-hop
      4. Merge context (entities + relations + graph expansion)
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        vectordb_engine: VectorDBEngine = None,
        graphdb_engine: GraphDBEngine = None,
        llm_client: BaseLLM = None
    ):
        if not self._initialized:
            self.vectordb = vectordb_engine or VectorDBEngine()
            self.graphdb = graphdb_engine or GraphDBEngine()
            self.embedding = HuggingFaceBgeEmbeddings(
                model_name=config.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
                query_instruction=""
            )
            self.llm = llm_client
            self.__class__._initialized = True
            logger.info("LightRAGRetrieval initialized")

    # =========================================================================
    # Main retrieval pipeline
    # =========================================================================

    async def retrieve(
        self, 
        subject_id: Annotated[str, Field(description="The subject id of the document supplied")],                    
        query: Annotated[str, Field(description="The query to retrieve document")] = None
    ) -> Dict[str, Any]:
        """
        Full LightRAG dual-level retrieval

        Returns:
            {context, low_level_docs, high_level_docs, graph_expansion, chunk_ids}
        """
        logger.info(f"Starting LightRAG retrieval for subject_id={subject_id}, query={query}")
        try:
            # Get subject name for filtering
            subject_id = get_subject_name_by_id(subject_id)
            top_k = config.DEFAULT_TOP_K
            filter_payload = {"subject_id": subject_id}

            # Step 1: Extract keywords
            local_kw, global_kw = await self._extract_keywords(query)
            logger.info(f"Keywords - local: {local_kw}, global: {global_kw}")

            # Step 2: Low-level retrieval (entities)
            low_query = " ".join(local_kw) if local_kw else query
            low_docs = await self.vectordb.retrieve_relevant_documents(
                query=low_query,
                embedding=self.embedding,
                collection_name=config.LOWLEVEL_COLLECTION_NAME,
                retrieval_mode=RetrievalMode.HYBRID,
                top_k=top_k,
                filter_payload=filter_payload,
            )
            entity_names = [
                d["metadata"]["entity_name"]
                for d in low_docs["docs"]
                if d["metadata"].get("entity_name")
            ]

            # Step 3: High-level retrieval (relations/themes)
            high_query = " ".join(global_kw) if global_kw else query
            high_docs = await self.vectordb.retrieve_relevant_documents(
                query=high_query,
                embedding=self.embedding,
                collection_name=config.HIGHLEVEL_COLLECTION_NAME,
                retrieval_mode=RetrievalMode.HYBRID,
                top_k=top_k,
                filter_payload=filter_payload,
            )
            relation_entities = set()
            for d in high_docs["docs"]:
                for key in ("source_entity", "target_entity"):
                    if d["metadata"].get(key):
                        relation_entities.add(d["metadata"][key])

            # Step 4: One-hop graph expansion
            all_names = list(set(entity_names) | relation_entities)
            graph_ctx = {"entities": [], "relations": []}
            if all_names:
                graph_ctx = await self.graphdb.get_one_hop(all_names, subject_id)

            # Step 5: Collect source chunk_ids
            chunk_ids = set()
            for d in low_docs["docs"]:
                chunk_ids.update(d["metadata"].get("chunk_ids", []))
            for d in high_docs["docs"]:
                cid = d["metadata"].get("chunk_id")
                if cid:
                    chunk_ids.add(cid)
                    
            logger.info(f"Retrieved {len(low_docs['docs'])} low-level docs, {len(high_docs['docs'])} high-level docs, graph expansion with {len(graph_ctx['entities'])} entities and {len(graph_ctx['relations'])} relations, total chunk_ids: {len(chunk_ids)}")
            logger.debug(f"Low-level docs: {[d['metadata'].get('entity_name') for d in low_docs['docs']]}") 
            
            # Step 6: Merge context
            return json.dumps(self._merge_context(
                low_docs["docs"], high_docs["docs"], graph_ctx, list(chunk_ids)
            ), ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error in LightRAG retrieval: {e}")
            return {
                "context": "",
                "low_level_docs": [],
                "high_level_docs": [],
                "graph_expansion": {"entities": [], "relations": []},
                "chunk_ids": [],
            }

    # =========================================================================
    # Keyword extraction (LLM)
    # =========================================================================

    async def _extract_keywords(self, query: str) -> Tuple[List[str], List[str]]:
        """Extract local + global keywords via LLM, fallback to raw query"""
        try:
            prompt = KEYWORD_PROMPT.format(query=query)
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            data = json.loads(response.content)
            return data.get("local_keywords", []), data.get("global_keywords", [])
        except Exception as e:
            logger.warning(f"Keyword extraction failed, using raw query: {e}")
            return [query], [query]

    # =========================================================================
    # Context merging
    # =========================================================================

    def _merge_context(
        self,
        query: str,
        low_docs: List[Dict],
        high_docs: List[Dict],
        graph_ctx: Dict,
        chunk_ids: List[str],
    ) -> Dict[str, Any]:
        """Merge low-level, high-level, and graph contexts into final output"""
        try:
            parts, seen = [], set()

            # Entity descriptions (low-level)
            for doc in low_docs:
                c = doc["content"]
                if c not in seen:
                    seen.add(c)
                    parts.append(f"[Entity] {c}")

            # Relation descriptions (high-level)
            for doc in high_docs:
                c = doc["content"]
                if c not in seen:
                    seen.add(c)
                    parts.append(f"[Relation] {c}")

            # Graph one-hop expansion
            for ent in graph_ctx.get("entities", []):
                desc = f"{ent['name']}: {ent.get('description', '')}"
                if desc not in seen:
                    seen.add(desc)
                    parts.append(f"[Graph Entity] {desc}")

            for rel in graph_ctx.get("relations", []):
                desc = f"{rel['source']} -[{rel['relation_type']}]-> {rel['target']}"
                if rel.get("description"):
                    desc += f": {rel['description']}"
                if desc not in seen:
                    seen.add(desc)
                    parts.append(f"[Graph Relation] {desc}")
                    
            logger.info(f"Length of merged context: {len(parts)} parts, total length: {sum(len(p) for p in parts)} chars")
                    
            return {
                "success": True,
                "tool_name": "lightRAG_retrieval",
                "content": "Tool lightRAG retrieval successful. The result has been displayed.",
                "query": query,
                "results_count": len(parts),
                "tool_result": "\n\n".join(parts)
            }
        except Exception as e:
            logger.error(f"Error merging contexts: {e}")
            return {
                "success": False,
                "tool_name": "lightRAG_retrieval",
                "content": "",
                "query": query,
                "results_count": 0,
                "tool_result": "",
            }
