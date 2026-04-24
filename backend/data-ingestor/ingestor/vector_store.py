# """
# vector_store.py – Manages the Qdrant collection and uploads LangChain Documents.
# """

# from __future__ import annotations

# from langchain_core.documents import Document
# from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# from langchain_qdrant import QdrantVectorStore, FastEmbedSparse
# from qdrant_client import QdrantClient
# from qdrant_client.http.models import (
#     Distance,
#     Filter,
#     FieldCondition,
#     MatchValue,
#     SparseIndexParams,
#     SparseVectorParams,
#     VectorParams,
# )
# from tqdm import tqdm

# from rag_config import (
#     QDRANT_HOST,
#     QDRANT_PORT,
#     QDRANT_COLLECTION_NAME,
#     EMBEDDING_MODEL,
#     EMBEDDING_DIM,
# )


# def _get_client() -> QdrantClient:
#     return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


# def _get_embeddings():
#     dense = HuggingFaceBgeEmbeddings(
#         model_name=EMBEDDING_MODEL,
#         model_kwargs={"trust_remote_code": True},
#     )
#     sparse = FastEmbedSparse()
#     return dense, sparse


# def ensure_collection(client: QdrantClient | None = None) -> None:
#     """Create the Qdrant collection if it does not exist."""
#     client = client or _get_client()
#     try:
#         client.get_collection(QDRANT_COLLECTION_NAME)
#         print(f"[qdrant] Collection '{QDRANT_COLLECTION_NAME}' already exists.")
#     except Exception:
#         client.create_collection(
#             collection_name=QDRANT_COLLECTION_NAME,
#             vectors_config={
#                 "dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
#             },
#             sparse_vectors_config={
#                 "sparse": SparseVectorParams(
#                     index=SparseIndexParams(on_disk=False),
#                 ),
#             },
#         )
#         print(f"[qdrant] Collection '{QDRANT_COLLECTION_NAME}' created.")


# def get_vector_store() -> QdrantVectorStore:
#     """Return a ready-to-use QdrantVectorStore instance."""
#     client = _get_client()
#     ensure_collection(client)
#     dense, sparse = _get_embeddings()
#     return QdrantVectorStore(
#         client=client,
#         collection_name=QDRANT_COLLECTION_NAME,
#         embedding=dense,
#         sparse_embedding=sparse,
#         vector_name="dense",
#         sparse_vector_name="sparse",
#     )


# def chunks_to_documents(chunks: list[str], subject: str, ref: str) -> list[Document]:
#     """Convert plain-text chunks into LangChain Documents with metadata."""
#     return [
#         Document(
#             page_content=chunk.strip(),
#             metadata={"subject": subject, "ref": ref},
#         )
#         for chunk in chunks
#         if chunk.strip()
#     ]


# def upload_documents(documents: list[Document], batch_size: int = 5) -> int:
#     """Upload documents to Qdrant in batches. Returns count uploaded."""
#     vs = get_vector_store()
#     total = len(documents)
#     print(f"[qdrant] Uploading {total} documents in batches of {batch_size}")

#     for i in tqdm(range(0, total, batch_size), desc="Uploading"):
#         batch = documents[i : i + batch_size]
#         vs.add_documents(batch)

#     print(f"[qdrant] All {total} documents uploaded.")
#     return total


# def search(query: str, subject: str | None = None, k: int = 10):
#     """Similarity search with optional subject filter."""
#     vs = get_vector_store()
#     filt = None
#     if subject:
#         filt = Filter(
#             must=[FieldCondition(key="metadata.subject", match=MatchValue(value=subject))]
#         )
#     return vs.similarity_search_with_score(query, k=k, filter=filt)
