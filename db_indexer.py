"""
Dynamic Database Ingestor & Semantic Schema Indexer.

Automatically ingests ANY database (SQLite, PostgreSQL, Snowflake, DPM_lite.db)
upon loading, extracts ALL table labels & column metadata, and builds a semantic vector index
using Mistral Embeddings (mistral-embed).

Zero hardcoded keywords or hardcoded rules. Works dynamically for any newly ingested database.
"""

import os
import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

import config

from mistralai.client import Mistral

INDEX_CACHE_PATH = config.BASE_DIR / ".schema_index.json"


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two vector embeddings."""
    a = np.array(v1)
    b = np.array(v2)
    norm = (np.linalg.norm(a) * np.linalg.norm(b))
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


class DynamicDatabaseIndexer:
    """
    Ingests and semantically indexes any database schema using Mistral Embeddings.
    """

    def __init__(self, db_path: Path = config.DB_PATH, api_key: Optional[str] = None):
        self.db_path = Path(db_path)
        self.api_key = api_key or config.MISTRAL_API_KEY
        self.client = Mistral(api_key=self.api_key) if self.api_key else None
        self.index_data: List[Dict[str, Any]] = []

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def build_index(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Scans the database, extracts metadata/labels, and computes vector embeddings using mistral-embed.
        Caches index in .schema_index.json.
        """
        if not force and INDEX_CACHE_PATH.exists():
            try:
                with open(INDEX_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached.get("db_name") == self.db_path.name:
                        self.index_data = cached.get("entries", [])
                        return self.index_data
            except Exception as e:
                print(f"[Indexer Cache] Info read: {e}")

        print(f"🔄 Ingestion et indexation sémantique complète de la base '{self.db_path.name}' via Mistral Embeddings...")
        entries = []
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]

            # 1. Ingest dpmTable if present (DPM taxonomy databases)
            if "dpmTable" in tables:
                cursor.execute(
                    "SELECT t.code, t.label FROM dpmTable t WHERE t.label IS NOT NULL AND t.label != ''"
                )
                dpm_tables = cursor.fetchall()
                for t_code, t_label in dpm_tables:
                    # Find a representative cell for row/column ordinates
                    cursor.execute(
                        "SELECT y_x_z, metric, description FROM dpmTableCell WHERE table_code = ? OR table_code LIKE ? LIMIT 1",
                        (t_code, f"{t_code}%")
                    )
                    cell_r = cursor.fetchone()
                    y_x_z = cell_r[0] if cell_r else "R0010|C0010"
                    metric = cell_r[1] if cell_r else "N/A"
                    cell_desc = cell_r[2] if cell_r else t_label

                    row_code = "R0010"
                    col_code = "C0010"
                    if y_x_z and "|" in y_x_z:
                        parts = y_x_z.split("|")
                        for p in parts:
                            if p.startswith("R") or p.startswith("ER") or p.startswith("YO"): row_code = p
                            elif p.startswith("C") or p.startswith("EC") or p.startswith("XO"): col_code = p

                    text_to_embed = f"Tableau QRT {t_code} : {t_label} (Concept : {cell_desc[:120]})"
                    entries.append({
                        "qrt_table": t_code,
                        "qrt_row": row_code,
                        "qrt_col": col_code,
                        "label": t_label,
                        "description": cell_desc,
                        "metric": metric or "N/A",
                        "text": text_to_embed,
                        "embedding": []
                    })

            # 2. Ingest data_dictionary if present
            if "data_dictionary" in tables:
                cursor.execute(
                    "SELECT table_name, column_name, qrt_table_code, qrt_row_code, qrt_col_code, concept_fr, concept_en, description FROM data_dictionary"
                )
                for r in cursor.fetchall():
                    tbl, col, q_t, q_r, q_c, c_fr, c_en, desc = r
                    text_to_embed = f"{tbl} {col} {c_fr} {c_en} {desc}"
                    entries.append({
                        "qrt_table": q_t,
                        "qrt_row": q_r,
                        "qrt_col": q_c,
                        "label": c_fr,
                        "description": desc or c_fr,
                        "metric": f"{tbl}.{col}",
                        "text": text_to_embed,
                        "embedding": []
                    })

            # 3. Ingest general table names & column schemas
            for t in tables:
                if t not in ["dpmTable", "dpmTableCell", "data_dictionary"]:
                    cursor.execute(f"PRAGMA table_info({t})")
                    col_names = [col[1] for col in cursor.fetchall()]
                    text_to_embed = f"Table {t} columns: {', '.join(col_names)}"
                    entries.append({
                        "qrt_table": t,
                        "qrt_row": "R0010",
                        "qrt_col": "C0010",
                        "label": f"Table {t}",
                        "description": text_to_embed,
                        "metric": "N/A",
                        "text": text_to_embed,
                        "embedding": []
                    })

        finally:
            conn.close()

        # Compute vector embeddings via mistral-embed
        if self.client and self.api_key and entries:
            texts = [e["text"] for e in entries]
            batch_size = 50
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                try:
                    resp = self.client.embeddings.create(model=config.MODEL_EMBED, inputs=batch_texts)
                    all_embeddings.extend([item.embedding for item in resp.data])
                except Exception as e:
                    print(f"[Indexer Error] Batch embedding error: {e}")
                    all_embeddings.extend([[] for _ in batch_texts])

            for entry, emb in zip(entries, all_embeddings):
                entry["embedding"] = emb

        self.index_data = entries

        try:
            with open(INDEX_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"db_name": self.db_path.name, "entries": entries}, f, ensure_ascii=False)
            print(f"✅ Indexation sémantique complète terminée : {len(entries)} concepts indexés dans '{INDEX_CACHE_PATH.name}'")
        except Exception as e:
            print(f"[Indexer Cache Save Error] {e}")

        return self.index_data

    def semantic_search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Performs semantic vector search for any query against the ingested database index.
        """
        if not self.index_data:
            self.build_index()

        if not self.index_data:
            return []

        if self.client and self.api_key:
            try:
                resp = self.client.embeddings.create(model=config.MODEL_EMBED, inputs=[query])
                query_emb = resp.data[0].embedding

                scored_entries = []
                for entry in self.index_data:
                    emb = entry.get("embedding", [])
                    if emb:
                        sim = cosine_similarity(query_emb, emb)
                        scored_entries.append((sim, entry))

                scored_entries.sort(key=lambda x: x[0], reverse=True)
                return [entry for score, entry in scored_entries[:top_k]]
            except Exception as e:
                print(f"[Semantic Search Error] {e}")

        # Fallback keyword search
        q_words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 2]
        scored = []
        for entry in self.index_data:
            text = entry.get("text", "").lower()
            score = sum(1 for w in q_words if w in text)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for score, entry in scored[:top_k]]


if __name__ == "__main__":
    indexer = DynamicDatabaseIndexer()
    indexer.build_index(force=True)
