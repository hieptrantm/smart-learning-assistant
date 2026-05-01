import os
import re
import json
import asyncio
import hashlib
import uuid
import logging
from typing import List, Dict
from collections import defaultdict

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams
from qdrant_client.http import models as qdrant_models
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse

from tqdm import tqdm
from services.llm_service import LLMService
from utils.treebase import TreeBasedEngine
from rag_config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_URL,
    HIGHLEVEL_COLLECTION_NAME, LOWLEVEL_COLLECTION_NAME,
    EMBEDDING_MODEL, EMBEDDING_DIMENSION,
    QDRANT_UPLOAD_BATCH_SIZE,
    PROFILING_SYSTEM_PROMPT, PROFILING_USER_PROMPT
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IndexingEngine:
    """
    LightRAG Indexing Pipeline.

    Flow:
      1. Extract Entities & Relations from each chunk (LLM)
      2. Deduplicate entities (LLM merge candidates)
      3. Profile entities (LLM reads ALL source chunks -> comprehensive description)
      4. Build high-level keys from relations (theme keywords)
      5. Save to Neo4j (entity nodes + relation edges + profiled descriptions)
      6. Index to Qdrant (low-level = entity keys, high-level = theme keys)
    """

    def __init__(self, llm=None, dense_emb_client=None, neo4j_client=None):
        self.llm = llm or LLMService(
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL_ID")
        )

        if QDRANT_URL:
            self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

        self._neo4j = neo4j_client or GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        self._dense_emb = dense_emb_client or HuggingFaceBgeEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"trust_remote_code": True}
            )
        self._sparse_emb = None
        self._low_vs = None
        self._high_vs = None
        self._raw_vs = None

        self.low_collection = LOWLEVEL_COLLECTION_NAME
        self.high_collection = HIGHLEVEL_COLLECTION_NAME

    # --- Lazy-loaded properties ---

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

    @property
    def sparse_emb(self):
        if self._sparse_emb is None:
            self._sparse_emb = FastEmbedSparse()
        return self._sparse_emb

    @property
    def low_vs(self):
        if self._low_vs is None:
            self._low_vs = QdrantVectorStore(
                client=self.qdrant,
                collection_name=self.low_collection,
                embedding=self.dense_emb,
                sparse_embedding=self.sparse_emb,
                vector_name="dense",
                sparse_vector_name="sparse"
            )
        return self._low_vs

    @property
    def high_vs(self):
        if self._high_vs is None:
            self._high_vs = QdrantVectorStore(
                client=self.qdrant,
                collection_name=self.high_collection,
                embedding=self.dense_emb,
                sparse_embedding=self.sparse_emb,
                vector_name="dense",
                sparse_vector_name="sparse"
            )
        return self._high_vs
    
    @property
    def raw_vs(self):
        if self._raw_vs is None:
            self._raw_vs = QdrantVectorStore(
                client=self.qdrant,
                collection_name="raw_chunks",
                embedding=self.dense_emb,
                sparse_embedding=self.sparse_emb,
                vector_name="dense",
                sparse_vector_name="sparse"
            )
        return self._raw_vs

    def close(self):
        if self._neo4j:
            self._neo4j.close()

    # --- Helpers ---

    def _create_collection(self, name, recreate=False):
        try:
            self.qdrant.get_collection(name)
            if recreate:
                self.qdrant.delete_collection(name)
            else:
                return
        except Exception:
            pass
        self.qdrant.create_collection(
            collection_name=name,
            vectors_config={
                "dense": VectorParams(
                    size=EMBEDDING_DIMENSION, distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=qdrant_models.SparseIndexParams(on_disk=False)
                )
            }
        )
        logger.info(f"Collection '{name}' created")

    def _gen_id(self, text):
        return hashlib.md5(f"{text}{uuid.uuid4()}".encode()).hexdigest()[:12]

    def _normalize(self, chunks, default_subject_id="Kinh tế Vi mô"):
        result = []
        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue
            content = chunk.get("text", chunk.get("content", ""))
            if not content.strip():
                continue
            result.append({
                "chunk_id": chunk.get("raw_chunk_id", chunk.get("chunk_id", f"chunk_{i}")),
                "content": content,
                "subject_id": chunk.get("subject_id", default_subject_id)
            })
        return result

    # =========================================================================
    # Step 1: Extract entities + relations from each chunk
    # =========================================================================

    async def _extract(self, chunks):
        chunk_texts = {}
        for chunk in chunks:
            chunk_texts[chunk["chunk_id"]] = chunk["content"]

        async def _extract_one(i, chunk):
            chunk_started = asyncio.get_running_loop().time()
            chunk_id = chunk["chunk_id"]
            content = chunk["content"]
            subject_id = chunk.get("subject_id", "")

            logger.info(f"Extracting chunk {i+1}/{len(chunks)}: {chunk_id}")
            logger.info(f"  -> requesting entities for {chunk_id} ({len(content)} chars)")

            raw_ents = await self.llm.aextract_entities_from_chunk(content)
            logger.info(f"  -> entity extraction finished for {chunk_id}: {len(raw_ents)} raw entities")
            ents = []
            for e in raw_ents:
                ents.append({
                    "name": e.get("name", "").strip(),
                    "type": e.get("type", "CONCEPT"),
                    "description": e.get("description", ""),
                    "chunk_id": chunk_id,
                    "subject_id": subject_id
                })

            rels = []
            if len(raw_ents) >= 2:
                logger.info(f"  -> requesting relations for {chunk_id} from {len(raw_ents)} entities")
                raw_rels = await self.llm.aextract_relations_from_chunk(raw_ents, content)
                logger.info(f"  -> relation extraction finished for {chunk_id}: {len(raw_rels)} raw relations")
                for r in raw_rels:
                    rels.append({
                        "source": r.get("source", ""),
                        "target": r.get("target", ""),
                        "relation_type": r.get("relation", "RELATED_TO"),
                        "description": r.get("description", ""),
                        "chunk_id": chunk_id,
                        "subject_id": subject_id
                    })
            else:
                logger.info(f"  -> skipping relation extraction for {chunk_id}: fewer than 2 entities")

            logger.info(
                f"  -> {len(ents)} entities, {len(rels)} relations for {chunk_id} in {asyncio.get_running_loop().time() - chunk_started:.2f}s"
            )
            return ents, rels

        # Fire all chunk extractions concurrently
        tasks = [_extract_one(i, chunk) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)

        entities = []
        relations = []
        for ents, rels in results:
            entities.extend(ents)
            relations.extend(rels)

        logger.info(f"Extraction total: {len(entities)} entities, {len(relations)} relations")
        return entities, relations, chunk_texts

    # =========================================================================
    # Step 2: Deduplicate entities (merge same concept with different names)
    # =========================================================================

    def _deduplicate(self, entities):
        groups = defaultdict(list)
        for e in entities:
            groups[e["name"]].append(e)

        unique_names = list(groups.keys())
        name_mapping = {}

        if len(unique_names) > 1:
            logger.info(f"Starting dedup merge-candidate detection for {len(unique_names)} unique names")
            merge_groups = self.llm.identify_merge_candidates(
                [{"name": n} for n in unique_names]
            )

            for group in merge_groups:
                if not isinstance(group, dict):
                    continue
                members = group.get("entities", [])
                canonical = group.get("canonical_name", "")
                reason = group.get("reason", "")

                if not canonical or not members:
                    continue

                for member in members:
                    if member in unique_names:
                        name_mapping[member] = canonical
                        logger.info(f"Merge: '{member}' -> '{canonical}' (reason: {reason})")

        for name in unique_names:
            if name not in name_mapping:
                name_mapping[name] = name

        canonical_groups = defaultdict(list)
        for name, ents in groups.items():
            canonical_groups[name_mapping.get(name, name)].extend(ents)

        logger.info(f"Dedup: {len(unique_names)} names -> {len(canonical_groups)} canonical entities")
        return canonical_groups, name_mapping
        # =========================================================================
    # Step 3: Profile entities (LLM reads ALL source chunks for each entity)
    # =========================================================================

    async def _profile(self, canonical_groups, chunk_texts):
        # Prepare all entity metadata first
        entity_metas = {}
        for name, entities in canonical_groups.items():
            chunk_ids = list(set(ent["chunk_id"] for ent in entities))
            aliases = list(set(ent["name"] for ent in entities if ent["name"] != name))
            subject_id = entities[0].get("subject_id", "")

            type_counts = defaultdict(int)
            for ent in entities:
                type_counts[ent["type"]] += 1
            entity_type = max(type_counts, key=type_counts.get)

            source_parts = []
            for cid in chunk_ids:
                if cid in chunk_texts:
                    source_parts.append(f"[{cid}]: {chunk_texts[cid]}")

            entity_metas[name] = {
                "entities": entities,
                "chunk_ids": chunk_ids,
                "aliases": aliases,
                "subject_id": subject_id,
                "entity_type": entity_type,
                "source_parts": source_parts,
            }

        # Async profiling task for a single entity
        async def _profile_one(name, meta):
            started = asyncio.get_running_loop().time()
            description = ""
            if meta["source_parts"]:
                logger.info(
                    "Profiling entity '%s' from %s chunks",
                    name,
                    len(meta["chunk_ids"]),
                )
                try:
                    description = await self.llm._acall_llm(
                        PROFILING_SYSTEM_PROMPT,
                        PROFILING_USER_PROMPT.format(
                            entity_name=name,
                            entity_type=meta["entity_type"],
                            source_chunks="\n\n".join(meta["source_parts"])[:15000]
                        ),
                        operation=f"profile_entity:{name}",
                    )
                except Exception as ex:
                    logger.warning(f"Profiling failed for '{name}': {ex}")
                    descs = [ent["description"] for ent in meta["entities"] if ent["description"]]
                    description = descs[0] if descs else ""
            logger.info(
                "Finished profiling '%s' in %.2fs",
                name,
                asyncio.get_running_loop().time() - started,
            )
            return name, {
                "description": description.strip(),
                "chunk_ids": meta["chunk_ids"],
                "aliases": meta["aliases"],
                "type": meta["entity_type"],
                "subject_id": meta["subject_id"]
            }

        # Fire all profiling calls concurrently
        tasks = [_profile_one(name, meta) for name, meta in entity_metas.items()]
        results = await asyncio.gather(*tasks)

        profiled = {name: info for name, info in results}
        logger.info(f"Profiled {len(profiled)} entities (async)")
        return profiled

    # =========================================================================
    # Step 4: Build high-level keys from relations
    # =========================================================================

    def _build_high_level(self, relations, name_mapping):
        items = []
        for rel in relations:
            src = name_mapping.get(rel["source"], rel["source"])
            tgt = name_mapping.get(rel["target"], rel["target"])
            rel_label = rel["relation_type"].lower().replace("_", " ")

            theme = f"{src} {rel_label} {tgt}"
            keywords = list(set(
                src.lower().split() + tgt.lower().split() + [rel_label]
            ))

            items.append({
                "theme": theme,
                "description": rel.get("description", "") or theme,
                "keywords": keywords,
                "source_entity": src,
                "target_entity": tgt,
                "relation_type": rel["relation_type"],
                "chunk_id": rel.get("chunk_id", ""),
                "subject_id": rel.get("subject_id", "")
            })

        logger.info(f"Built {len(items)} high-level keys")
        return items

    # =========================================================================
    # Step 5: Save to Neo4j (entities as nodes, relations as edges)
    # =========================================================================

    def _save_neo4j(self, profiled, relations, name_mapping, subject_id=None, clear=False):
        with self.neo4j.session() as session:
            if clear and subject_id:
                session.run(
                    "MATCH (n:Entity {subject_id: $subject_id}) DETACH DELETE n",
                    subject_id=subject_id
                )
                logger.info(f"Neo4j: cleared all nodes for subject_id={subject_id}")
            elif clear:
                session.run("MATCH (n) DETACH DELETE n")

            # Entity nodes with profiled descriptions (keyed by name + subject_id)
            for name, info in profiled.items():
                sid = info.get("subject_id") or subject_id or ""
                session.run(
                    """MERGE (e:Entity {name: $name, subject_id: $subject_id})
                    SET e.type = $type,
                        e.description = $description,
                        e.chunk_ids = $chunk_ids,
                        e.aliases = $aliases""",
                    name=name, type=info["type"],
                    description=info["description"],
                    chunk_ids=info["chunk_ids"],
                    aliases=info["aliases"],
                    subject_id=sid
                )

            # Relation edges (scoped by subject_id)
            edge_count = 0
            for rel in relations:
                src = name_mapping.get(rel["source"], rel["source"])
                tgt = name_mapping.get(rel["target"], rel["target"])
                sid = rel.get("subject_id") or subject_id or ""
                rel_type = re.sub(r'[^A-Z0-9_]', '_', rel["relation_type"].upper())
                if not rel_type or rel_type[0].isdigit():
                    rel_type = "REL_" + rel_type

                try:
                    session.run(
                        f"""MATCH (s:Entity {{name: $src, subject_id: $sid}})
                        MATCH (t:Entity {{name: $tgt, subject_id: $sid}})
                        MERGE (s)-[r:{rel_type}]->(t)
                        SET r.description = $desc,
                            r.chunk_id = $chunk_id""",
                        src=src, tgt=tgt, sid=sid,
                        desc=rel.get("description", ""),
                        chunk_id=rel.get("chunk_id", "")
                    )
                    edge_count += 1
                except Exception as ex:
                    logger.warning(f"Neo4j edge failed ({src}->{tgt}): {ex}")

        logger.info(f"Neo4j: {len(profiled)} nodes, {edge_count} edges saved (subject_id={subject_id})")

    # =========================================================================
    # Step 6: Index to Qdrant (low-level entities + high-level themes)
    # =========================================================================

    def _index_qdrant(self, profiled, high_level_items, chunks, recreate=True, subject_id=None):
        logger.info(f"Data profiled: {profiled}")
        self._create_collection(self.low_collection, recreate)
        self._create_collection(self.high_collection, recreate)
        self._create_collection("raw_chunks", recreate)
        self._low_vs = None
        self._high_vs = None

        # Low-level: entity name + profiled description
        low_docs = []
        for name, info in profiled.items():
            low_docs.append(Document(
                page_content=f"{name}. {info['description']}",
                metadata={
                    "entity_name": name,
                    "type": info["type"],
                    "description": info["description"],
                    "chunk_ids": info["chunk_ids"],
                    "aliases": info["aliases"],
                    "subject_id": info["subject_id"] or subject_id
                }
            ))

        batches = range(0, len(low_docs), QDRANT_UPLOAD_BATCH_SIZE)
        for i in tqdm(batches, desc="Indexing low-level entities", unit="batch"):
            self.low_vs.add_documents(low_docs[i:i + QDRANT_UPLOAD_BATCH_SIZE])
        logger.info(f"Qdrant low-level: {len(low_docs)} entities indexed")

        # High-level: relationship theme + description
        high_docs = []
        for item in high_level_items:
            high_docs.append(Document(
                page_content=f"{item['theme']}. {item['description']}",
                metadata={
                    "theme": item["theme"],
                    "description": item["description"],
                    "keywords": item["keywords"],
                    "source_entity": item["source_entity"],
                    "target_entity": item["target_entity"],
                    "relation_type": item["relation_type"],
                    "chunk_id": item["chunk_id"],
                    "subject_id": item["subject_id"] or subject_id
                }
            ))
        batches = range(0, len(high_docs), QDRANT_UPLOAD_BATCH_SIZE)
        for i in tqdm(batches, desc="Indexing high-level themes", unit="batch"):
            self.high_vs.add_documents(high_docs[i:i + QDRANT_UPLOAD_BATCH_SIZE])
        logger.info(f"Qdrant high-level: {len(high_docs)} themes indexed")
            
        # Raw chunks
        raw_docs = []
        for chunk in chunks:
            raw_docs.append(Document(
                page_content=chunk["text"],
                metadata={
                    "chunk_id": chunk["raw_chunk_id"],
                    "subject_id": subject_id 
                }
            ))

        batches = range(0, len(raw_docs), QDRANT_UPLOAD_BATCH_SIZE)
        for i in tqdm(batches, desc="Indexing raw chunks", unit="batch"):
            self.raw_vs.add_documents(raw_docs[i:i + QDRANT_UPLOAD_BATCH_SIZE])
        logger.info(f"Qdrant raw chunks: {len(raw_docs)} chunks indexed")


    # =========================================================================
    # Step 7: Tree-based representation
    # =========================================================================

    async def _build_tree_background(self, subject_id: str):
        """Run TreeBasedEngine to build tree from the knowledge graph."""
        try:
            logger.info(f"Building tree-based representation for subject_id={subject_id}")
            tree_engine = TreeBasedEngine(llm_client=self.llm.client)
            tree_subject_id = await tree_engine.run(subject_id)
            logger.info(f"Tree-based representation saved under subject_id={tree_subject_id}")
        except Exception as ex:
            logger.warning(f"Tree-based indexing failed: {ex}")

    # =========================================================================
    # Main entry point
    # =========================================================================

    async def ingest(self, chunks, subject_id: str, save_to_neo4j=True,
               save_kg_json=None, recreate=True):
        """
        Run full indexing pipeline.

        Args:
            chunks: list of dicts {raw_chunk_id/chunk_id, text/content, subject_id}
            subject_id: default subject_id if not in chunks
            save_to_neo4j: save graph to Neo4j
            save_kg_json: path to save intermediate KG as JSON
            recreate: recreate Qdrant collections and clear Neo4j
        """
        logger.info(f"=== IndexingEngine: {len(chunks)} chunks ===")

        normalized = self._normalize(chunks, subject_id)
        if not normalized:
            return {"error": "No valid chunks"}

        # Step 1: Extract (async - all chunks processed concurrently)
        entities, relations, chunk_texts = await self._extract(normalized)
        logger.info(f"Step 1 complete: {len(entities)} entities, {len(relations)} relations extracted")
        

        # Step 2: Deduplicate
        canonical_groups, name_mapping = self._deduplicate(entities)
        logger.info(f"canonical groups: {len(canonical_groups)}")

        # Step 3: Profile (async - all entities profiled concurrently)
        profiled = await self._profile(canonical_groups, chunk_texts)

        # Step 4: High-level keys
        high_level = self._build_high_level(relations, name_mapping)

        # Save intermediate KG
        if save_kg_json:
            self._save_kg_json(save_kg_json, profiled, relations, high_level)

        # Step 5: Neo4j
        if save_to_neo4j:
            self._save_neo4j(profiled, relations, name_mapping, subject_id=subject_id, clear=recreate)
            await self._build_tree_background(subject_id)

        # Step 6: Qdrant
        self._index_qdrant(profiled, high_level, chunks, recreate, subject_id=subject_id)  

        # Step 7: Build tree-based representation (must complete before planner)
        # if save_to_neo4j:
        
        stats = {
            "chunks": len(normalized),
            "entities_raw": len(entities),
            "entities_profiled": len(profiled),
            "relations": len(relations),
            "high_level_keys": len(high_level)
        }
        logger.info(f"=== Ingestion complete: {json.dumps(stats)} ===")
        return stats

    def _save_kg_json(self, path, profiled, relations, high_level):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "profiled_entities": profiled,
                "relations": relations,
                "high_level_keys": high_level
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"KG saved to {path}")


def load_chunks_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "chunks" in data:
        return data["chunks"]
    return []


if __name__ == "__main__":
    subject = "Kinh tế Vi mô"
    chunks_file = f"output/{subject}_raw_chunks.json"
    if not os.path.exists(chunks_file):
        chunks_file = "raw_chunk.json"

    if os.path.exists(chunks_file):
        chunks = load_chunks_from_json(chunks_file)
        print(f"Loaded {len(chunks)} chunks from {chunks_file}")

        engine = IndexingEngine()
        try:
            stats = asyncio.run(engine.ingest(
                chunks,
                subject_id=subject,
                save_to_neo4j=True,
                save_kg_json=f"output/{subject}_knowledge_graph.json",
                recreate=True
            ))
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        finally:
            engine.close()
    else:
        print(f"Chunks file not found: {chunks_file}")
