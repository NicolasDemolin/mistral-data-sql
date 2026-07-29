"""
ACPR Local Tool Functions.
These functions are registered via RunContext.register_func() so that
Mistral AI agents can call them automatically during conversations.
Each function docstring serves as the tool description seen by the model.
"""

import json
from typing import Optional
from si_connector import SQLiteSIConnector
from config import DB_PATH

_connector = SQLiteSIConnector(db_path=DB_PATH)


def list_available_tables() -> str:
    """List all available tables in the ACPR regulatory database.
    Returns a JSON array of table names.
    """
    tables = _connector.list_tables()
    return json.dumps({"tables": tables})


def get_table_columns(table_name: str) -> str:
    """Get the column definitions (name and type) for a specific table in the ACPR database.

    Args:
        table_name: name of the database table (e.g. s2301_own_funds, s0201_balance_sheet, entities, data_dictionary)
    """
    columns = _connector.get_table_schema(table_name)
    return json.dumps({"table": table_name, "columns": columns})


def get_schema_metadata(concept: str) -> str:
    """Search the ACPR regulatory metadata dictionary for entries matching a financial concept.
    Returns matching table names, column names, QRT codes, and descriptions.

    Args:
        concept: the financial or regulatory concept to search for in French (e.g. 'fonds propres', 'total actif', 'ratio solvabilité', 'tier 1')
    """
    try:
        cols, rows = _connector.execute_query(
            "SELECT table_name, column_name, qrt_table_code, qrt_row_code, qrt_col_code, "
            "concept_fr, concept_en, unit, description FROM data_dictionary"
        )
        concept_lower = concept.lower()
        matches = []
        for r in rows:
            text = f"{r[5]} {r[6]} {r[8]}".lower()
            if any(word in text for word in concept_lower.split() if len(word) > 2):
                matches.append({
                    "table_name": r[0], "column_name": r[1],
                    "qrt_table_code": r[2], "qrt_row_code": r[3], "qrt_col_code": r[4],
                    "concept_fr": r[5], "concept_en": r[6], "unit": r[7], "description": r[8]
                })
        return json.dumps({"concept_searched": concept, "matches": matches}, ensure_ascii=False)
    except Exception:
        # Fallback for DPM_lite.db
        try:
            cols, rows = _connector.execute_query(
                "SELECT code, label FROM dpmTable WHERE label LIKE ? LIMIT 10",
                (f"%{concept}%",)
            )
            matches = [{"table_code": r[0], "table_label": r[1]} for r in rows]
            return json.dumps({"concept_searched": concept, "matches": matches}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"concept_searched": concept, "matches": [], "error": str(e)}, ensure_ascii=False)


def lookup_qrt_coordinates(table_name: str, column_name: str) -> str:
    """Look up the exact ACPR/EIOPA Solvency II QRT cell coordinates for a given table and column.

    Args:
        table_name: the database table name (e.g. s2301_own_funds)
        column_name: the database column name (e.g. total_eligible_own_funds_scr)
    """
    try:
        cols, rows = _connector.execute_query(
            f"SELECT qrt_table_code, qrt_row_code, qrt_col_code, concept_fr, unit, description "
            f"FROM data_dictionary WHERE table_name = ? AND column_name = ?",
            (table_name, column_name)
        )
        if rows:
            r = rows[0]
            return json.dumps({
                "qrt_table_code": r[0], "qrt_row_code": r[1], "qrt_col_code": r[2],
                "concept_fr": r[3], "unit": r[4], "description": r[5]
            }, ensure_ascii=False)
    except Exception:
        pass
    return json.dumps({"error": f"No QRT coordinates found for {table_name}.{column_name}"})


def get_entity_info(entity_name: str) -> str:
    """Get information about a financial entity (insurer) by name.
    Returns the entity's LEI code, full name, country, and sector.

    Args:
        entity_name: the name or partial name of the entity (e.g. 'AXA', 'ALLIANZ', 'GENERALI')
    """
    pattern = f"%{entity_name.upper()}%"
    cols, rows = _connector.execute_query(
        "SELECT lei_code, name, short_code, country, sector FROM entities WHERE UPPER(name) LIKE ?",
        (pattern,)
    )
    results = []
    for r in rows:
        results.append({
            "lei_code": r[0], "name": r[1], "short_code": r[2],
            "country": r[3], "sector": r[4]
        })
    return json.dumps({"query": entity_name, "entities": results}, ensure_ascii=False)


def query_database(sql_query: str) -> str:
    """Execute a read-only SQL SELECT query against the ACPR regulatory database and return the results.
    ONLY SELECT queries are allowed. The database contains tables: entities, s2301_own_funds, s0201_balance_sheet, data_dictionary.

    Args:
        sql_query: a valid SQL SELECT query to execute
    """
    try:
        cols, rows = _connector.execute_query(sql_query)
        results = [dict(zip(cols, row)) for row in rows]
        return json.dumps({"columns": cols, "row_count": len(rows), "results": results}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
