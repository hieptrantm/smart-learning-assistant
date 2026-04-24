import logging
import asyncio
from typing import List, Dict, Any, Optional

from neo4j import GraphDatabase

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphDBEngine:
    """
    Neo4j graph database engine for knowledge graph retrieval
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new GraphDBEngine instance")
            cls._instance = super(GraphDBEngine, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        neo4j_uri: str = config.NEO4J_URI,
        neo4j_user: str = config.NEO4J_USER,
        neo4j_password: str = config.NEO4J_PASSWORD,
    ):
        if not self._initialized:
            self.driver = GraphDatabase.driver(
                neo4j_uri, auth=(neo4j_user, neo4j_password)
            )
            self.__class__._initialized = True
            logger.info("GraphDBEngine initialized")

    def close(self):
        if self.driver:
            self.driver.close()

    def _read(self, query_fn):
        """Execute a read transaction"""
        with self.driver.session() as session:
            return session.execute_read(query_fn)

    # =========================================================================
    # Entity queries
    # =========================================================================

    async def find_entities(
        self, names: List[str], subject_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find entities by names, filtered by subject_id"""
        def _q(tx):
            cypher = (
                "MATCH (e:Entity) WHERE e.name IN $names"
                + (" AND e.subject_id = $sid" if subject_id else "")
                + " RETURN e.name AS name, e.type AS type, "
                  "e.description AS description, e.chunk_ids AS chunk_ids"
            )
            return [dict(r) for r in tx.run(cypher, names=names, sid=subject_id)]

        return await asyncio.to_thread(self._read, _q)

    # =========================================================================
    # One-hop expansion
    # =========================================================================

    async def get_one_hop(
        self, entity_names: List[str], subject_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get one-hop neighbors (entities + edges) for given entities

        Returns:
            {entities: [...], relations: [...]}
        """
        def _q(tx):
            cypher = (
                "MATCH (e:Entity)-[r]-(n:Entity) WHERE e.name IN $names"
                + (" AND e.subject_id = $sid" if subject_id else "")
                + " RETURN e.name AS src, type(r) AS rel_type, "
                  "r.description AS rel_desc, r.chunk_id AS chunk_id, "
                  "n.name AS neighbor, n.type AS n_type, n.description AS n_desc"
            )
            return [dict(r) for r in tx.run(cypher, names=entity_names, sid=subject_id)]

        raw = await asyncio.to_thread(self._read, _q)

        entities, relations = {}, []
        for row in raw:
            if row["neighbor"] and row["neighbor"] not in entities:
                entities[row["neighbor"]] = {
                    "name": row["neighbor"],
                    "type": row["n_type"],
                    "description": row["n_desc"]
                }
            if row["rel_type"]:
                relations.append({
                    "source": row["src"],
                    "target": row["neighbor"],
                    "relation_type": row["rel_type"],
                    "description": row["rel_desc"],
                    "chunk_id": row["chunk_id"]
                })

        return {"entities": list(entities.values()), "relations": relations}
