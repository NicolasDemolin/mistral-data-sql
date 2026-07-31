"""
Pydantic I/O Models for the Mistral Text-to-Data Workflow.
"""
from typing import Optional
from pydantic import BaseModel

class TextToDataInput(BaseModel):
    """Input schema for the workflow."""
    query: str


class SchemaDiscoveryResult(BaseModel):
    """Output of the schema discovery activity."""
    all_tables: list[str]
    schemas: dict
    dpm_specialist_info: Optional[dict] = None


class SQLGenerationResult(BaseModel):
    """Output of the SQL generation activity."""
    sql_query: str


class QueryExecutionResult(BaseModel):
    """Output of the query execution activity."""
    sql_query: str
    columns: list[str]
    rows: list[list]  # list of rows as lists (JSON-serializable)


class EvaluationResult(BaseModel):
    """Output of the evaluation activity."""
    reasoning: str
    is_correct: bool
    confidence_score: float


class TextToDataOutput(BaseModel):
    """Final structured output of the workflow."""
    original_query: str
    entity_name: str
    concept: str
    value: float
    formatted_value: str
    currency: str
    period: str
    lei_code: str
    qrt_table: str
    qrt_row: str
    qrt_col: str
    sql_query: str
    reasoning: str
    confidence: float
    rows_data: list[dict]
    audit_trail: list[str]
