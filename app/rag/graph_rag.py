"""
Graph RAG module using Neo4j to query entity relationships.
Demonstrates structured query execution to complement vector search.
"""
import os
from typing import Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


class Neo4jGraphRAG:
    """Enterprise Graph RAG connection driver utilizing Neo4j Cypher queries."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self.enabled = GraphDatabase is not None and bool(self.uri) and bool(self.password)
        self.driver = None

        if self.enabled:
            print("[*] Neo4j Graph Database driver ready for connection.")
        else:
            print("[*] Neo4j library not installed or environment variables missing. Graph RAG bypassed.")

    def connect(self):
        """Establish session connection to Neo4j graph db."""
        if self.enabled and self.driver is None:
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
                print("[OK] Neo4j graph database driver successfully initialized.")
            except Exception as e:
                print(f"[!] Failed to connect to Neo4j database: {e}")
                self.enabled = False

    def query_relationships(self, entity_name: str) -> list[dict]:
        """
        Execute a Cypher query to retrieve all direct relationships for a specific entity.
        Useful to complement semantic retrieval with structured facts (e.g. ownership, governance).
        """
        if not self.enabled:
            return []

        self.connect()
        if self.driver is None:
            return []

        query = (
            "MATCH (e {name: $entity_name})-[r]->(target) "
            "RETURN type(r) AS relationship, target.name AS target_name, labels(target)[0] AS target_type "
            "LIMIT 10"
        )
        
        relationships = []
        try:
            with self.driver.session() as session:
                result = session.run(query, entity_name=entity_name)
                for record in result:
                    relationships.append({
                        "source": entity_name,
                        "relationship": record["relationship"],
                        "target": record["target_name"],
                        "target_type": record["target_type"]
                    })
            return relationships
        except Exception as e:
            print(f"[!] Cypher query failed: {e}")
            return []

    def close(self):
        """Close connection driver."""
        if self.driver:
            self.driver.close()
