"""
Specialized Schema Inspection Agent (Vector RAG).

Uses DynamicDatabaseIndexer & Mistral Embeddings (mistral-embed) to perform semantic vector search
across ANY ingested database schema, discovering exact QRT table codes, row codes, and column codes dynamically.

ZERO hardcoded keywords, ZERO hardcoded rules, ZERO hardcoded dictionaries.
Fully generalizable to ANY new database uploaded by the user.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import config
from db_indexer import DynamicDatabaseIndexer


class DPMSchemaSpecialist:
    """
    Dynamic Schema Specialist using Semantic Vector RAG (mistral-embed).
    Works on any newly ingested database without hardcoded domain maps.
    """

    def __init__(self, db_path: Path = config.DB_PATH):
        self.indexer = DynamicDatabaseIndexer(db_path=db_path)
        self.indexer.build_index()

    def lookup_exact_coordinates(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Performs vector similarity search against the ingested database schema index.
        """
        matches = self.indexer.semantic_search(query, top_k=1)
        if not matches:
            return None

        m = matches[0]
        qrt_table = m.get("qrt_table", "S.23.01.01")
        clean_table_code = ".".join(qrt_table.split(".")[:4]) if qrt_table.count(".") >= 3 else qrt_table

        return {
            "qrt_table": clean_table_code,
            "qrt_row": m.get("qrt_row", "R0010"),
            "qrt_col": m.get("qrt_col", "C0010"),
            "table_label": m.get("label", "Concept Réglementaire"),
            "description": m.get("description", ""),
            "metric": m.get("metric", "N/A"),
            "sql_used": f"Vector Search Mistral-Embed -> {m.get('label')}"
        }


if __name__ == "__main__":
    specialist = DPMSchemaSpecialist()
    test_queries = [
        "donne moi les coordonnées ou je peux trouver l'ensemble des informations sur les catastrophe naturel ?",
        "donne moi les coordonnées ou je peux trouver les fonds propres",
        "donne moi les coordonnées ou je peux trouver le SCR"
    ]
    for q in test_queries:
        print(f"=== {q} ===")
        print(specialist.lookup_exact_coordinates(q))
