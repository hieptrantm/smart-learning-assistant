from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from app.services.llm_client import create_llm_client
from langchain_core.messages import HumanMessage, SystemMessage
import json


COLLECTION_NAME = "VTIDocument"
EMBEDDING_MODEL = "AITeamVN/Vietnamese_Embedding_v2"
EMBEDDING_DIM = 1024  # bge-m3 dimension
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

class QdrantService:
    def __init__(self, dense_embedding=None, sparse_embedding=None):
        self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.sparse_embedding = sparse_embedding or FastEmbedSparse()
        self.dense_embedding = dense_embedding or HuggingFaceBgeEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"trust_remote_code": True}
        )
        self.llm_client = create_llm_client()
        
    def summary_document(self, document):
        user_prompt = f"Hãy tóm tắt ngắn gọn nội dung trên.{document}"
        messages = [
            HumanMessage(content=user_prompt)
        ]
        response = self.llm_client.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
        
    def search_by_subject(self, query: str = "", collection_name=None, subject_id=None, k=10):
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.subject_id",
                    match=MatchValue(value=subject_id),
                )
            ]
        )

        vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=self.dense_embedding,
            sparse_embedding=self.sparse_embedding,
            vector_name="dense",
            sparse_vector_name="sparse",
            retrieval_mode=RetrievalMode.HYBRID,
        )

        results = vector_store.similarity_search_with_score(
            query,
            k=k,
            filter=qdrant_filter,
        )
        return results
    
    def search_multiple_collections(self, query: str = "", collection_names=None, subject_id=None, k=10):
        all_results = []
        for collection_name in collection_names:
            results = self.search_by_subject(query, collection_name, subject_id, k)
            for doc, score in results:
                all_results.append({
                    "collection_name": collection_name,
                    "document": doc,
                    "score": score,
                })
        
        # Sort results by score in descending order
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        return all_results[:k]

    @staticmethod
    def extract_chunk_ids(metadata):
        chunk_ids = []

        single_chunk_id = metadata.get("chunk_id")
        if isinstance(single_chunk_id, str) and single_chunk_id:
            chunk_ids.append(single_chunk_id)

        multiple_chunk_ids = metadata.get("chunk_ids", [])
        if isinstance(multiple_chunk_ids, list):
            chunk_ids.extend(
                chunk_id for chunk_id in multiple_chunk_ids if isinstance(chunk_id, str) and chunk_id
            )
        elif isinstance(multiple_chunk_ids, str) and multiple_chunk_ids:
            chunk_ids.append(multiple_chunk_ids)

        return list(dict.fromkeys(chunk_ids))
        
    async def gather_context(self, query: str, subject_id: str) -> str:
        query = query or ""
        COLLECTION_NAMES = ["low-level-retrieval", "high-level-retrieval"]
        aggregated_results = []
        
        raw_chunks = self.search_by_subject(query, "raw_chunks", subject_id, k=5)
        # Sort by chunk_id
        raw_chunks.sort(key=lambda x: x[0].metadata.get("chunk_id", ""))
        context_results = self.search_multiple_collections(query, COLLECTION_NAMES, subject_id, k=100)

        for i, (doc, score) in enumerate(raw_chunks, start=1):
            content = doc.page_content
            chunk_id = doc.metadata.get("chunk_id", "")

            summary = self.summary_document(content)
            low_level_contexts = []
            high_level_contexts = []
            matched_contexts = []

            for context_result in context_results:
                context_doc = context_result["document"]
                context_score = context_result["score"]
                collection_name = context_result["collection_name"]
                context_chunk_ids = self.extract_chunk_ids(context_doc.metadata)

                if chunk_id not in context_chunk_ids:
                    continue

                context_item = {
                    "label": context_doc.metadata.get("theme") or context_doc.metadata.get("entity_name"),
                    "content": context_doc.metadata.get("description"),
                }
                matched_contexts.append(context_item)

                if collection_name == "low-level-retrieval":
                    low_level_contexts.append(context_item)
                elif collection_name == "high-level-retrieval":
                    high_level_contexts.append(context_item)

            aggregated_results.append({
                "chunk_id": chunk_id,
                "summary": summary,
                "contexts": matched_contexts,
            })

            # print(f"- Summary {i}: {summary}")
            # print(f"- Chunk id: {chunk_id}")
            # print(f"- Low level contexts: {len(low_level_contexts)}")
            # print(f"- High level contexts: {len(high_level_contexts)}")

        # print("===============")
        return json.dumps(aggregated_results, ensure_ascii=False, indent=2, default=str)