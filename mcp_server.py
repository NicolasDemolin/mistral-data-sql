"""
Model Context Protocol (MCP) Server for ACPR Text-to-Data.

Exposes custom ACPR tools (get_entity_info, get_schema_metadata, query_database, lookup_qrt_coordinates)
via the official MCP standard (FastMCP) so Vibe Coding, Cursor, VSCode, or Mistral AI
can connect to and execute custom database tools natively.
"""

import json
from mcp.server.fastmcp import FastMCP
import tools

# Create FastMCP server instance
mcp = FastMCP("ACPR Text-to-Data MCP Server")


@mcp.tool()
def get_entity_info(entity_name: str) -> str:
    """Get legal entity information (LEI code, name, country, sector) by name.
    
    Args:
        entity_name: Name of insurer or group (e.g. 'AXA', 'ALLIANZ', 'GENERALI')
    """
    return tools.get_entity_info(entity_name)


@mcp.tool()
def get_schema_metadata(concept: str) -> str:
    """Search ACPR Solvency II data dictionary for matches with a financial concept.
    
    Args:
        concept: Concept in French (e.g. 'fonds propres', 'total actif', 'ratio solvabilité')
    """
    return tools.get_schema_metadata(concept)


@mcp.tool()
def lookup_qrt_coordinates(table_name: str, column_name: str) -> str:
    """Look up exact ACPR/EIOPA Solvency II QRT cell coordinates for a table and column.
    
    Args:
        table_name: Database table name (e.g. 's2301_own_funds')
        column_name: Database column name (e.g. 'total_eligible_own_funds_scr')
    """
    return tools.lookup_qrt_coordinates(table_name, column_name)


@mcp.tool()
def query_database(sql_query: str) -> str:
    """Execute a read-only SQL SELECT query against the ACPR database.
    
    Args:
        sql_query: Valid SQL SELECT query
    """
    return tools.query_database(sql_query)


@mcp.tool()
def list_available_tables() -> str:
    """List all available tables in the ACPR regulatory database."""
    return tools.list_available_tables()


@mcp.tool()
def get_table_columns(table_name: str) -> str:
    """Get column definitions for a specific ACPR database table."""
    return tools.get_table_columns(table_name)


if __name__ == "__main__":
    # Run standalone stdio MCP server for Vibe Coding / Cursor integration
    mcp.run(transport="stdio")
