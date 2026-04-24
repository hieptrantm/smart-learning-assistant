import logging
import asyncio
from typing import List, Dict, Any, Optional

from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse
from langchain_openai import OpenAIEmbeddings
from qdrant_client.http import models as qdrant_models
from qdrant_client import QdrantClient

import config
try:
    from transformers import AutoTokenizer
except ImportError:
    AutoTokenizer = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VECTOR_NAME = "dense"

class VectorDBEngine:
    """
    Vector database engine for document storage and retrieval
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new VectorDBEngine instance")
            cls._instance = super(VectorDBEngine, cls).__new__(cls)
        return cls._instance

    def __init__(
            self,
            qdrant_host: str = config.QDRANT_HOST,
            qdrant_port: int = config.QDRANT_PORT,
            qdrant_collection_name: str = config.QDRANT_COLLECTION_NAME,
            # qdrant_api_key: Optional[str] = config.QDRANT_API_KEY,
    ):
        if not self._initialized:
            self.sparse_embeddings = FastEmbedSparse()

            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(
                url=qdrant_host,
                port=qdrant_port,
                # api_key=qdrant_api_key,
            )

            self.qdrant_collection_name = qdrant_collection_name

            self.__class__._initialized = True
            logger.info("VectorDBEngine initialized")

    async def retrieve_relevant_documents(
            self, 
            query: str,
            embedding: OpenAIEmbeddings,
            collection_name: str = config.QDRANT_COLLECTION_NAME,
            retrieval_mode: RetrievalMode = RetrievalMode.DENSE,
            top_k: int = config.DEFAULT_TOP_K, 
            filter_payload: Optional[Dict[str, Any]] = None, 
            use_MMR: bool = False, 
            use_reranking: bool = False,
            prioritize_table: Optional[bool] = False
            ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query

        Args:
            query: User query to retrieve documents for
            top_k: Number of documents to retrieve

        Returns:
            List of relevant documents with content and metadata
        """

        vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=embedding,
            sparse_embedding=self.sparse_embeddings if 
            (retrieval_mode == RetrievalMode.HYBRID or retrieval_mode == RetrievalMode.SPARSE) 
            else None,
            retrieval_mode=retrieval_mode,
            sparse_vector_name="sparse",
            vector_name=VECTOR_NAME
        )

        qdrant_filter = None
        
        if filter_payload:
            must_conditions = []
            # should_conditions = []

            # Handle subject_id filter
            if "subject_id" in filter_payload:
                must_conditions.append(
                    qdrant_models.FieldCondition(
                        key="metadata.subject_id",
                        match=qdrant_models.MatchValue(value=filter_payload["subject_id"])
                    )
                )
            # Create the filter with all conditions
            qdrant_filter = qdrant_models.Filter(
                must=must_conditions,
                should=[],
                must_not=[]
            )

        if use_MMR:
            # Get embedding vector for the query
            print("==============MMR==============")
            query_embedding = await asyncio.to_thread(
                embedding.embed_query,
                query
            )

            docs = await asyncio.to_thread(
                vector_store.max_marginal_relevance_search_with_score_by_vector,
                query_embedding,
                k=top_k,
                fetch_k=top_k + 5,
                filter=qdrant_filter
            )
            print("==============MMR==============")
        else:
            docs = await asyncio.to_thread(
                vector_store.similarity_search_with_score,
                query,
                k=top_k,
                filter=qdrant_filter
            )

        results = []

        for doc_infor in docs:
            results.append({
                "content": doc_infor[0].page_content,
                "metadata": doc_infor[0].metadata,
                "embedding_score": doc_infor[1]
            })

        if prioritize_table:
            list_condition = []
            list_sources = []
            list_page_label = []
            list_page_label_str = []
            for doc_infor in docs:
                if "page_label" not in doc_infor[0].metadata.keys():
                    continue
                if not doc_infor[0].metadata["sources"] in list_sources:
                    list_sources.append(doc_infor[0].metadata["sources"])
                if doc_infor[0].metadata["page_label"] not in list_page_label:
                    list_page_label_str.append(str(doc_infor[0].metadata["page_label"]))
                    list_page_label.append(int(doc_infor[0].metadata["page_label"]))
            list_condition.append(qdrant_models.FieldCondition(
                    key="metadata.sources",
                    match=qdrant_models.MatchAny(any=list_sources)
                ))
            list_condition.append(qdrant_models.FieldCondition(
                    key="metadata.page_label",
                    match=qdrant_models.MatchAny(any=list_page_label)
                ))
            list_condition.append(qdrant_models.FieldCondition(
                    key="metadata.page_label",
                    match=qdrant_models.MatchAny(any=list_page_label_str)
                ))
            list_condition.append(qdrant_models.FieldCondition(
                    key="metadata.docling_item_types",
                    match=qdrant_models.MatchAny(any=["table"])
                ))
            qdrant_table_pages_filter = qdrant_models.Filter(
                should=[],
                must_not=[],
                must=list_condition
            )
            if use_MMR:
                # Get embedding vector for the query
                query_embedding = await asyncio.to_thread(
                    embedding.embed_query,
                    ""
                )

                docs_table = await asyncio.to_thread(
                    vector_store.max_marginal_relevance_search_with_score_by_vector,
                    query_embedding,
                    k=50,
                    fetch_k=55,
                    filter=qdrant_table_pages_filter
                )
            else:
                docs_table = await asyncio.to_thread(
                    vector_store.similarity_search_with_score,
                    "",
                    k=50,
                    filter=qdrant_table_pages_filter
                )
            for doc in docs_table:
                results.append({
                    "content": doc[0].page_content,
                    "metadata": doc[0].metadata,
                    "embedding_score": 0
                })

        return {
                "docs": results
            }
