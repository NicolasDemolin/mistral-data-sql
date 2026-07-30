"""
ACPR Text-to-Data — Mistral AI Studio Workflow.

This module defines a durable Workflow using the `mistralai-workflows` SDK.
It is orchestrated by the Mistral control plane and executed by a worker
running on your own infrastructure (DigitalOcean Droplet).

Pipeline:
  1. discover_schema  — Scan DPM_lite.db + DPMSchemaSpecialist semantic search
  2. generate_sql     — Call Codestral to produce exact SQL SELECT
  3. execute_query    — Run the SQL on DPM_lite.db (with auto-correction retry)
  4. synthesize       — Format structured JSON response with QRT coordinates
"""

import os
import json
import re
from typing import Optional
from datetime import timedelta

import mistralai.workflows as workflows
from pydantic import BaseModel

# ── Pydantic I/O Models ─────────────────────────────────────────────────

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


# ── Activities ───────────────────────────────────────────────────────────

@workflows.activity(start_to_close_timeout=timedelta(seconds=30))
async def discover_schema(input: TextToDataInput) -> SchemaDiscoveryResult:
    """
    Activity 1: Discover database schema and perform semantic DPM lookup.
    Side-effects: reads DPM_lite.db, calls mistral-embed for vector search.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402
    from si_connector import SQLiteSIConnector
    from dpm_specialist import DPMSchemaSpecialist

    connector = SQLiteSIConnector(db_path=config.DB_PATH)
    available_tables = connector.list_tables()

    db_schemas = {}
    for table in available_tables:
        try:
            db_schemas[table] = connector.get_table_schema(table)
        except Exception:
            pass

    # Deep taxonomy lookup via DPMSchemaSpecialist (semantic vector search)
    dpm_info = None
    try:
        specialist = DPMSchemaSpecialist(db_path=config.DB_PATH)
        dpm_info = specialist.lookup_exact_coordinates(input.query)
    except Exception:
        pass

    return SchemaDiscoveryResult(
        all_tables=available_tables,
        schemas=db_schemas,
        dpm_specialist_info=dpm_info,
    )


@workflows.activity(start_to_close_timeout=timedelta(seconds=60))
async def generate_sql(query: str, schema_info: dict, previous_error: Optional[str] = None) -> SQLGenerationResult:
    """
    Activity 2: Use Codestral to generate an exact SQL SELECT query.
    Side-effects: calls Mistral Codestral API.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402

    client = config.get_mistral_client()

    system_prompt = (
        "Tu es un expert SQL Codestral universel. Ta mission est de générer une requête SQL SELECT brute "
        "pour répondre à la question de l'utilisateur d'après la structure de la base ci-jointe.\n\n"
        "Règles d'or SQL :\n"
        "1. Ne mets AUCUN commentaire (pas de -- ni de /* */) ni d'explication textuelle. Renvoie SEULEMENT le code SQL SELECT pur.\n"
        "2. Gère la traduction FR/EN si la base est en anglais (ex: 'fonds propres' = 'own funds' / 'S.23.01', 'bilan' = 'balance sheet').\n"
        "3. Si la base est un modèle DPM (dpmTable, dpmTableCell), fais les JOIN nécessaires.\n"
        "4. Limite les résultats (`LIMIT 10`).\n\n"
        f"Structure des tables de la base :\n{json.dumps(schema_info.get('schemas', {}), indent=2, ensure_ascii=False)}\n\n"
    )

    if schema_info.get("dpm_specialist_info"):
        system_prompt += f"Inspection Spécialiste DPM :\n{json.dumps(schema_info['dpm_specialist_info'], ensure_ascii=False)}\n\n"

    if previous_error:
        system_prompt += f"⚠️ ATTENTION : La tentative précédente a échoué avec l'erreur SQL suivante :\n{previous_error}\nCorrige la requête SQL.\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question : '{query}'"},
    ]

    response = client.chat.complete(
        model=config.MODEL_CODE,
        messages=messages,
        response_format={"type": "text"},
        temperature=0.0,
    )
    sql = response.choices[0].message.content.strip()

    # Clean markdown code blocks and comments
    if "```" in sql:
        sql = sql.split("```sql")[-1].split("```")[0].strip()
    sql = re.sub(r"^--.*$", "", sql, flags=re.MULTILINE).strip()

    return SQLGenerationResult(sql_query=sql)


@workflows.activity(start_to_close_timeout=timedelta(seconds=15))
async def execute_query(sql_query: str) -> QueryExecutionResult:
    """
    Activity 3: Execute a read-only SQL SELECT on DPM_lite.db.
    Side-effects: reads DPM_lite.db.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402
    from si_connector import SQLiteSIConnector

    connector = SQLiteSIConnector(db_path=config.DB_PATH)
    cols, rows = connector.execute_query(sql_query)

    # Convert tuples to lists for JSON serialization
    serializable_rows = [list(r) for r in rows]
    return QueryExecutionResult(
        sql_query=sql_query,
        columns=cols,
        rows=serializable_rows,
    )


@workflows.activity(start_to_close_timeout=timedelta(seconds=10))
async def synthesize_result(
    query: str,
    sql_query: str,
    columns: list[str],
    rows: list[list],
    dpm_specialist_info: Optional[dict],
) -> TextToDataOutput:
    """
    Activity 4: Synthesize the final structured response with QRT coordinates.
    Pure computation, no side-effects.
    """
    audit_trail = [
        f"1. Query: '{query}'",
        f"2. SQL: {sql_query}",
        f"3. Rows returned: {len(rows)}",
    ]

    if not rows:
        qrt_t = dpm_specialist_info["qrt_table"] if dpm_specialist_info else "N/A"
        qrt_r = dpm_specialist_info["qrt_row"] if dpm_specialist_info else "N/A"
        qrt_c = dpm_specialist_info["qrt_col"] if dpm_specialist_info else "N/A"
        concept = dpm_specialist_info["table_label"] if dpm_specialist_info else "N/A"
        audit_trail.append("4. No data rows found")

        return TextToDataOutput(
            original_query=query,
            entity_name="Non trouvée",
            concept=concept,
            value=0.0,
            formatted_value="Aucune donnée correspondante",
            currency="EUR",
            period="2023-Q4",
            lei_code="N/A",
            qrt_table=qrt_t,
            qrt_row=qrt_r,
            qrt_col=qrt_c,
            sql_query=sql_query,
            reasoning=f"0 résultat trouvé pour '{query}'",
            confidence=0.0,
            rows_data=[],
            audit_trail=audit_trail,
        )

    first_row = dict(zip(columns, rows[0]))

    # Entity / primary name
    entity_name = "Toutes entités / Taxonomie DPM"
    for key in ["name", "entity_name", "table_label", "table_code", "label", "code"]:
        if key in first_row and first_row[key]:
            entity_name = str(first_row[key])
            break

    # LEI / Identifier
    lei_code = "N/A"
    for key in ["lei_code", "lei", "id", "code", "table_code"]:
        if key in first_row and first_row[key]:
            lei_code = str(first_row[key])
            break

    # Numeric value
    amount = 0.0
    currency = str(first_row.get("currency", "EUR"))
    period = str(first_row.get("period", "2023-Q4"))
    numeric_found = False

    for k, v in first_row.items():
        if isinstance(v, (int, float)) and k not in ["id", "entity_id"]:
            amount = float(v)
            numeric_found = True
            break

    # QRT coordinates
    if dpm_specialist_info:
        qrt_table = dpm_specialist_info["qrt_table"]
        qrt_row = dpm_specialist_info["qrt_row"]
        qrt_col = dpm_specialist_info["qrt_col"]
        concept_desc = f"{dpm_specialist_info['table_label']} - {dpm_specialist_info.get('description', '')[:60]}"
    else:
        qrt_table = str(first_row.get("table_code", first_row.get("code", "N/A")))
        qrt_row = "R0010"
        qrt_col = "C0010"
        y_x_z = str(first_row.get("y_x_z", ""))
        if y_x_z and "|" in y_x_z:
            for p in y_x_z.split("|"):
                if p.startswith("R"):
                    qrt_row = p
                elif p.startswith("C"):
                    qrt_col = p
        concept_desc = str(first_row.get("description", first_row.get("table_label", "Concept réglementaire")))

    # Format display value
    if numeric_found and amount != 0:
        if amount >= 1e9:
            fmt_val = f"{amount / 1e9:,.2f} Mds {currency}"
        elif amount >= 1e6:
            fmt_val = f"{amount / 1e6:,.2f} M€"
        else:
            fmt_val = f"{amount:,.2f} {currency}"
    else:
        fmt_val = f"{len(rows)} cellule(s) QRT identifiée(s)"

    audit_trail.append(f"4. QRT: {qrt_table} / {qrt_row} / {qrt_col}")

    return TextToDataOutput(
        original_query=query,
        entity_name=entity_name,
        concept=concept_desc,
        value=amount,
        formatted_value=fmt_val,
        currency=currency,
        period=period,
        lei_code=lei_code,
        qrt_table=qrt_table,
        qrt_row=qrt_row,
        qrt_col=qrt_col,
        sql_query=sql_query,
        reasoning=f"Workflow DPM : '{query}' → {qrt_table}/{qrt_row}/{qrt_col}",
        confidence=1.0 if rows else 0.0,
        rows_data=[dict(zip(columns, r)) for r in rows[:5]],
        audit_trail=audit_trail,
    )


# ── Workflow ─────────────────────────────────────────────────────────────

@workflows.workflow.define(
    name="acpr-text-to-data",
    workflow_display_name="ACPR Text-to-Data",
    workflow_description=(
        "Pipeline déterministe Text-to-Data pour la taxonomie Solvabilité II (EIOPA DPM). "
        "Découvre le schéma, génère le SQL via Codestral, exécute la requête, "
        "et retourne les coordonnées QRT précises."
    ),
)
class ACPRTextToDataWorkflow:
    """
    Durable Workflow orchestrating 4 activities:
    discover_schema → generate_sql → execute_query → synthesize_result
    """

    @workflows.workflow.entrypoint
    async def run(self, input: TextToDataInput) -> TextToDataOutput:
        # Step 1: Discover schema + DPM specialist semantic search
        schema_result = await discover_schema(input)

        # Step 2: Generate SQL via Codestral
        schema_dict = schema_result.model_dump()
        sql_result = await generate_sql(
            query=input.query,
            schema_info=schema_dict,
        )

        # Step 3: Execute query with auto-correction (up to 2 retries)
        max_retries = 2
        query_result = None
        previous_error = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Re-generate SQL with the error context
                    sql_result = await generate_sql(
                        query=input.query,
                        schema_info=schema_dict,
                        previous_error=previous_error,
                    )
                query_result = await execute_query(sql_query=sql_result.sql_query)
                break  # Success
            except Exception as e:
                previous_error = str(e)
                if attempt == max_retries:
                    # Final failure: return empty result
                    query_result = QueryExecutionResult(
                        sql_query=sql_result.sql_query,
                        columns=[],
                        rows=[],
                    )

        # Step 4: Synthesize final structured response
        result = await synthesize_result(
            query=input.query,
            sql_query=query_result.sql_query,
            columns=query_result.columns,
            rows=query_result.rows,
            dpm_specialist_info=schema_result.dpm_specialist_info,
        )

        return result
