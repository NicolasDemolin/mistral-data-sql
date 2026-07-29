"""
SI Abstraction Layer for ACPR Reporting Database.
Allows swapping SQLite for PostgreSQL, Snowflake, Oracle, DB2, Databricks, or BigQuery.
"""

import sqlite3
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any
from config import DB_PATH


class SIConnector:
    """Abstract Base Class for Enterprise SI Connectors."""
    def list_tables(self) -> List[str]:
        raise NotImplementedError
    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        raise NotImplementedError
    def execute_query(self, sql_query: str, params: Tuple = ()) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        raise NotImplementedError


class SQLiteSIConnector(SIConnector):
    """SQLite Implementation of SIConnector."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def execute_query(self, sql_query: str, params: Tuple = ()) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        # Strip comments (-- or /* */) to extract core SQL statement
        cleaned = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL).strip().upper()

        if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
            raise ValueError("Only read-only SELECT queries are allowed in regulatory execution mode.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql_query, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return columns, rows
        finally:
            conn.close()

    def list_tables(self) -> List[str]:
        cols, rows = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        return [r[0] for r in rows]

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            rows = cursor.fetchall()
            return [{"column_name": r[1], "data_type": r[2]} for r in rows]
        finally:
            conn.close()
