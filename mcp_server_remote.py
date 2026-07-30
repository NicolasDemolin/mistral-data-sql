"""
MCP Server for remote deployment (SSE transport over HTTP).
Exposes ACPR/DPM tools via the Model Context Protocol standard.
Designed to run inside a Docker container on DigitalOcean.
"""

import os
import json
from mcp.server.fastmcp import FastMCP

# Force DATABASE_PATH to DPM_lite.db for this deployment
os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")

import config  # noqa: E402  — must come after env override
import tools   # noqa: E402

# Create FastMCP server with SSE transport support
mcp = FastMCP(
    "ACPR DPM Text-to-Data MCP Server",
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", "8080")),
)


@mcp.tool()
def list_available_tables() -> str:
    """List all available tables in the DPM regulatory database.
    Returns a JSON array of table names.
    """
    return tools.list_available_tables()


@mcp.tool()
def get_table_columns(table_name: str) -> str:
    """Get column definitions (name and type) for a specific table.

    Args:
        table_name: Name of the database table (e.g. dpmTable, dpmTableCell, dpmDimension)
    """
    return tools.get_table_columns(table_name)


@mcp.tool()
def get_schema_metadata(concept: str) -> str:
    """Search the DPM taxonomy for tables matching a financial/regulatory concept.

    Args:
        concept: Financial concept in French or English (e.g. 'fonds propres', 'own funds', 'catastrophe')
    """
    return tools.get_schema_metadata(concept)


@mcp.tool()
def lookup_qrt_coordinates(table_name: str, column_name: str) -> str:
    """Look up exact EIOPA Solvency II QRT cell coordinates for a table and column.

    Args:
        table_name: Database table name (e.g. 's2301_own_funds')
        column_name: Database column name (e.g. 'total_eligible_own_funds_scr')
    """
    return tools.lookup_qrt_coordinates(table_name, column_name)


@mcp.tool()
def query_database(sql_query: str) -> str:
    """Execute a read-only SQL SELECT query against the DPM database and return results.
    ONLY SELECT queries are allowed.

    Args:
        sql_query: A valid SQL SELECT query to execute
    """
    return tools.query_database(sql_query)


@mcp.tool()
def get_entity_info(entity_name: str) -> str:
    """Get information about a financial entity (insurer) by name.

    Args:
        entity_name: Name or partial name of the entity (e.g. 'AXA', 'ALLIANZ')
    """
    return tools.get_entity_info(entity_name)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "sse")
    print(f"🚀 Starting MCP Server (transport={transport}, port={os.environ.get('MCP_PORT', '8080')})")
    print(f"📦 Database: {config.DB_PATH}")
    mcp.run(transport=transport)
