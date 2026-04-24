from typing import Annotated, List, Dict, Any, Optional
import logging

from pydantic import Field
from langchain_qdrant import RetrievalMode
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

from vectordb.engine import VectorDBEngine
import config

# from reranker.engine import RerankEngine
# from metadata_extractor.engine import MetaDataFilterEngine
# from hyde.engine import HyDEEngine
# from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocSearchTool:
    """
    Standalone RAG tool for document search and retrieval
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new DocSearchTool instance")
            cls._instance = super(DocSearchTool, cls).__new__(cls)
        return cls._instance

    def __init__(
            self,
            vectordb_engine: VectorDBEngine,
            # filter_pipeline: MetaDataFilterEngine,
            # hyde_engine: HyDEEngine,
            # rerank_engine: Optional[RerankEngine] = None
    ):
        if not self._initialized:
            self.vectordb = vectordb_engine
            # self.filter_pipeline = filter_pipeline
            # self.hyde_engine = hyde_engine
            # self.rerank_engine = rerank_engine
            
            # Initialize embedding model
            self.embedding = HuggingFaceBgeEmbeddings(
                model_name=config.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
                query_instruction=""
            )
            
            self.__class__._initialized = True
            logger.info("Initialized DocSearchTool")
    
    # temporarily turn off for retrieval_settings 
    async def retrieve(self, 
                      embedding: Any,
                      query: str, 
                      top_k: int = config.DEFAULT_TOP_K, 
                      filter_payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query
        """
        # mock setting
        retrieval_mode = "hybrid"
        use_MMR =  False
        use_reranking = False
        prioritize_table = False

        mapping_retrieval_mode = {
            "vector": RetrievalMode.DENSE,
            "hybrid": RetrievalMode.HYBRID,
            "text": RetrievalMode.SPARSE
        }

        docs = await self.vectordb.retrieve_relevant_documents(
            query,
            embedding,
            mapping_retrieval_mode[retrieval_mode],
            top_k,
            filter_payload,
            use_MMR,
            use_reranking,
            prioritize_table
        )
        
        return docs

    async def search_documents(self,
            subject_id: Annotated[str, Field(description="The subject or topic to search documents for")],                    
            query: Annotated[str, Field(description="The query to retrieve document")] = None):
        """
        This method use to search knowledge from subject documents, then prepare the evidence text to be used in answer generation.
        """
        try:
            try:
                # try:
                #     try:
                #         hyDE_document= self.hyde_engine._create_hyde_documents(question=query)
                #     except Exception as e:
                #         logger.error(f"Get HyDE document error: {str(e)}")
                #     logger.info(f"Hyde Document info: \n Hyde content: {hyDE_document} \n Hyde Type: {type(hyDE_document)}")
                # except Exception as e:
                #     logger.error(f"Failed in get hyde doc: {str(e)}")

                # Question classification
                # filtered_metadata = self.filter_pipeline.__call__(query)
                # logger.info(f"Filtered metadata: {filtered_metadata}")
                metadtata_filter = {
                    "subject_id": subject_id
                }

                # Retrieve relevant documents
                res_retrieve = await self.retrieve(
                    embedding=self.embedding,
                    query=str(query),
                    top_k=config.DEFAULT_TOP_K,
                    filter_payload=metadtata_filter
                )
            except Exception as e:
                logger.error(f"Error in retrieving for documents: {str(e)}")

            relevant_docs = res_retrieve["docs"]

            # Remove duplicate documents
            seen_contents = set()
            unique_docs = []
            
            for doc in relevant_docs:
                content = doc.get('content', '').strip()
                if content and content not in seen_contents:
                    seen_contents.add(content)
                    unique_docs.append(doc)

            # # Rerank documents if rerank engine is provided
            # try:
            #     if self.rerank_engine:
            #         logger.info(f"Reranking {len(unique_docs)} unique documents")
            #         unique_docs = self.rerank_engine.rerank(
            #             query=query,
            #             docs=unique_docs
            #         )
            # except Exception as e:
            #     logger.error(f"Reranking error: {str(e)}")

            logger.info(f"Found {len(unique_docs)} unique relevant documents. \n Document contents: {[doc.get('content', '')[:50] for doc in unique_docs]}")

            return {
                "success": True,
                "content": self.format_documents_retrieved(unique_docs),
                "sources": [{
                    "type": "docsearch",
                    "metadata": doc.get("metadata", {}),
                    "content": doc.get("content", "No content"),
                    "embedding_score": doc.get("embedding_score", 0.0),
                    "relevance_score": doc.get("relevance_score")
                } for doc in unique_docs]
            }
                   
        except Exception as e:
            logger.error(f"DocSearch error: {str(e)}")
            return {
                "success": False,
                "error": f"Error in document search: {str(e)}",
                "content": f"Document search failed: {str(e)}"
            }

    def format_documents_retrieved(self, docs: List[Dict[str, Any]], trim_len: int = 15000) -> str:
        """
        Prepare evidence text from retrieved documents
        
        Args:
            docs: List of document dictionaries
            trim_len: Maximum length to trim evidence
            
        Returns:
            Formatted evidence string
        """
        evidence = ""
        for i, doc in enumerate(docs):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown file")
            ref = metadata.get("ref", "https://vms.vti.com.vn/myvti")
            similarity_score = f"{doc.get('embedding_score', 0.0):.2f}"
            
            doc_text = f"[{file_name}]({ref}) (Similarity: {similarity_score}):\n{content}\n\n"
            
            # Check if adding this document would exceed trim_len
            if len(evidence) + len(doc_text) > trim_len:
                remaining_len = trim_len - len(evidence)
                if remaining_len > 100:  # Only add if there's meaningful space left
                    evidence += doc_text[:remaining_len] + "...\n\n"
                break
            
            evidence += doc_text
            
        return evidence.strip()
    
if __name__ == "__main__":
    rag = DocSearchTool(
        vectordb_engine=VectorDBEngine()
    )
    
    import asyncio
    res = asyncio.run(rag.search_documents(
        subject_id="cổ tích",
        query="Bà cụ mỉm cười, chạm nhẹ vào bát cơm trên bàn."
    ))
    
    print("Search result: ", res)
    